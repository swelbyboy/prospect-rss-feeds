#!/usr/bin/env python3
"""
Main scraper orchestrator.
Coordinates scraping, RSS generation, and publishing workflow.
"""

import csv
import os
import re
import sys
import time
from datetime import datetime
from firecrawl import FirecrawlApp
from config import Config
from rss_generator import RSSFeedGenerator
from github_publisher import GitHubPublisher


class ProspectScraper:
    """Main orchestrator for scraping prospect websites and generating RSS feeds."""

    def __init__(self):
        """Initialize the scraper with required components."""
        try:
            Config.validate()
        except ValueError as e:
            print(f"❌ Configuration error: {e}")
            sys.exit(1)

        self.firecrawl = FirecrawlApp(api_key=Config.FIRECRAWL_API_KEY)
        self.rss_generator = RSSFeedGenerator()
        self.github_publisher = GitHubPublisher()
        self.tracking_data = []

    def load_prospects(self):
        """
        Load prospects from CSV file.

        Returns:
            list: List of prospect dictionaries
        """
        prospects = []
        try:
            with open(Config.PROSPECTS_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                prospects = list(reader)
            print(f"📋 Loaded {len(prospects)} prospects from {Config.PROSPECTS_CSV}")
            return prospects
        except FileNotFoundError:
            print(f"❌ Prospects file not found: {Config.PROSPECTS_CSV}")
            print("Please create a prospects.csv file with columns: id, company_name, domain")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error loading prospects: {e}")
            sys.exit(1)

    def scrape_articles(self, prospect):
        """
        Scrape articles from a prospect's website using Firecrawl.

        Strategy:
        1. Scrape the homepage to find article links
        2. Filter for likely article URLs
        3. Scrape top 10 article pages for full content

        Args:
            prospect (dict): Prospect information

        Returns:
            tuple: (success: bool, articles: list, error_message: str)
        """
        domain = prospect['domain']
        company_name = prospect['company_name']

        print(f"\n🔍 Scraping {company_name} ({domain})...")

        try:
            # Ensure domain has protocol
            if not domain.startswith('http'):
                url = f'https://{domain}'
            else:
                url = domain

            # Step 1: Scrape homepage to find article links
            print(f"   📄 Scraping homepage...")

            homepage_params = {
                'formats': ['markdown', 'links']
            }

            # Retry with exponential backoff for queue timeout
            max_retries = 3
            retry_delay = 10
            homepage_result = None

            for attempt in range(max_retries):
                try:
                    homepage_result = self.firecrawl.scrape_url(url, params=homepage_params)
                    break  # Success!
                except Exception as e:
                    if '408' in str(e) and attempt < max_retries - 1:
                        print(f"   ⏳ Queue busy, waiting {retry_delay}s before retry {attempt + 2}/{max_retries}...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise  # Re-raise if not a 408 or final attempt

            if not homepage_result:
                return False, [], "No data returned from homepage scrape"

            # Extract links from homepage (key is 'linksOnPage' in Firecrawl)
            links = homepage_result.get('linksOnPage', [])
            if not links:
                return False, [], "No links found on homepage"

            print(f"   🔗 Found {len(links)} links on homepage")

            # Step 2: Filter for article links
            article_urls = self._filter_article_links(links, url, domain)

            if not article_urls:
                print(f"   ⚠️  No article links found for {company_name}")
                return False, [], "No article links detected on homepage"

            print(f"   📰 Identified {len(article_urls)} potential article links")

            # Limit to MAX_ARTICLES_PER_PROSPECT
            article_urls = article_urls[:Config.MAX_ARTICLES_PER_PROSPECT]

            # Step 3: Scrape each article page
            articles = []
            for idx, article_url in enumerate(article_urls, 1):
                print(f"   📖 Scraping article {idx}/{len(article_urls)}...")
                try:
                    article_result = self.firecrawl.scrape_url(
                        article_url,
                        params={'formats': ['markdown']}
                    )

                    if article_result:
                        metadata = article_result.get('metadata', {})
                        markdown_content = article_result.get('markdown', '')

                        # Validate that this is actual article content
                        if not self._is_valid_article(metadata, markdown_content, article_url):
                            print(f"   ⚠️  Skipping - not a valid article (likely navigation/utility page)")
                            continue

                        articles.append({
                            'title': metadata.get('title', f"Article {idx}"),
                            'link': article_url,
                            'description': metadata.get('description', '')[:200],
                            'published_date': metadata.get('publishedTime'),
                            'image_url': metadata.get('ogImage') or metadata.get('image', '')
                        })

                    # Small delay to be nice to Firecrawl API
                    time.sleep(1)

                except Exception as e:
                    print(f"   ⚠️  Failed to scrape article {idx}: {str(e)}")
                    continue

            if not articles:
                print(f"   ⚠️  No articles scraped successfully for {company_name}")
                return False, [], "Failed to scrape any articles"

            print(f"   ✅ Successfully scraped {len(articles)} articles")
            return True, articles, None

        except Exception as e:
            error_msg = f"Scraping error: {str(e)}"
            print(f"   ❌ {error_msg}")
            return False, [], error_msg

    def _filter_article_links(self, links, homepage_url, domain):
        """
        Filter links from homepage to find potential article URLs.

        Strategy: Keep filtering minimal - only exclude obvious non-articles.
        Content validation will filter out the rest after scraping.

        Args:
            links (list): List of link URLs from homepage
            homepage_url (str): The homepage URL
            domain (str): Domain being scraped

        Returns:
            list: List of article URL strings
        """
        article_urls = []

        # Minimal exclusions - only obvious non-article pages
        exclude_patterns = [
            # Static/utility pages
            '/about', '/contact', '/privacy', '/terms', '/login',
            '/signup', '/register', '/search', '/subscribe', '/schedule',
            '/disclaimer', '/advertise', '/advertising',
            # Administrative
            '/tag/', '/category/', '/author/', '/page/', '/community/',
            '/feed', '/rss', '/api/', '/wp-admin', '/wp-content',
            # Media files
            '.pdf', '.jpg', '.png', '.gif', '.zip', '.xml', '.css', '.js',
            # External links
            'facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com',
            'youtube.com', 'mailto:', 'tel:',
        ]

        for link in links:
            if not link or not isinstance(link, str):
                continue

            link_lower = link.lower()

            # Skip if it's the homepage itself
            homepage_base = homepage_url.rstrip('/')
            link_base = link.rstrip('/')
            if link_base == homepage_base or link_base + '#' == homepage_base:
                continue

            # Skip if it's just a language code (e.g., /en, /en-us, /fr)
            if re.match(r'^https?://[^/]+/[a-z]{2}(-[a-z]{2,3})?/?$', link_base):
                continue

            # Skip external links (must be same domain)
            if link.startswith('http') and domain not in link:
                continue

            # Skip excluded patterns
            if any(pattern in link_lower for pattern in exclude_patterns):
                continue

            # Skip very short paths or single-segment paths (likely sections/categories)
            path = link.replace(homepage_url, '').split('?')[0].strip('/')

            # Too short = navigation
            if len(path) < 5:  # e.g., /news, /blog
                continue

            # Single short segment = likely a category/section page
            path_segments = [s for s in path.split('/') if s]
            if len(path_segments) == 1 and len(path_segments[0]) < 20:
                # Single segment like "/venezuela" or "/sports" - likely a category
                continue

            # Accept everything else - let content validation handle it
            # Ensure full URL
            if link.startswith('/'):
                full_url = homepage_url.rstrip('/') + link
            elif not link.startswith('http'):
                full_url = homepage_url.rstrip('/') + '/' + link
            else:
                full_url = link

            # Avoid duplicates
            if full_url not in article_urls:
                article_urls.append(full_url)

        return article_urls

    def _is_valid_article(self, metadata, markdown_content, url):
        """
        Validate that scraped content is a legitimate article suitable for a newsletter.

        This is the PRIMARY filter - it must be thorough since URL filtering is minimal.

        Args:
            metadata (dict): Article metadata from Firecrawl
            markdown_content (str): Article markdown content
            url (str): Article URL

        Returns:
            bool: True if valid article, False otherwise
        """
        # Get title and description
        title = metadata.get('title', '').lower()
        description = metadata.get('description', '').lower()
        url_lower = url.lower()

        # 1. RED FLAGS IN TITLES - Explicit non-article indicators
        non_article_title_patterns = [
            'home', 'homepage', 'listen live', 'schedule', 'on air', 'on-air',
            'what\'s on', 'events', 'calendar', 'win ', 'competition',
            'subscribe', 'newsletter', 'contact us', 'about us',
            'privacy policy', 'terms', 'cookie policy', 'smart speaker',
            'advertise', 'careers', 'jobs', '404', 'not found',
            'all articles', 'archive', 'sitemap', 'categories'
        ]

        for pattern in non_article_title_patterns:
            if pattern in title:
                return False

        # 2. RED FLAGS IN URLs - Common navigation patterns
        url_navigation_patterns = [
            '/listen', '/schedule', '/on-air', '/calendar', '/events',
            '/win-', '/competition', '/categories/', '/sections/',
            '/archive', '/all-news', '/all-articles'
        ]

        for pattern in url_navigation_patterns:
            if pattern in url_lower:
                return False

        # 3. TITLE QUALITY - Must be descriptive
        if len(title) < 10:
            return False

        # Title should have at least 3 words
        title_word_count = len(title.split())
        if title_word_count < 3:
            return False

        # 4. CONTENT LENGTH - Articles must have substantial content
        content_words = markdown_content.split() if markdown_content else []
        word_count = len(content_words)

        # Minimum 150 words for articles
        if word_count < 150:
            return False

        # 5. LINK DENSITY - Reject pages that are mostly links
        if markdown_content:
            link_count = markdown_content.count('](')
            # If more than 20% of content is links, likely a navigation/index page
            if word_count > 0 and (link_count / (word_count / 5)) > 0.2:
                return False

        # 6. METADATA SIGNALS - Look for article indicators
        has_published_date = bool(metadata.get('publishedTime') or metadata.get('published'))
        has_description = len(description) > 30
        has_author = bool(metadata.get('author') or metadata.get('author'))

        # Strong signal: has pub date
        if has_published_date:
            return True

        # Decent signals: description + reasonable content
        if has_description and word_count >= 200:
            return True

        # Weak but acceptable: just lots of content
        if word_count >= 400:
            return True

        # Not enough signals to be confident it's an article
        return False

    def process_prospect(self, prospect):
        """
        Process a single prospect: scrape, generate RSS, track results.

        Args:
            prospect (dict): Prospect information

        Returns:
            dict: Tracking information for this prospect
        """
        prospect_id = prospect['id']
        company_name = prospect['company_name']
        domain = prospect['domain']

        # Scrape articles
        success, articles, error_message = self.scrape_articles(prospect)

        # Prepare tracking entry
        tracking_entry = {
            'prospect_id': prospect_id,
            'company_name': company_name,
            'domain': domain,
            'last_scrape_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'success' if success else 'failed',
            'articles_found': len(articles) if success else 0,
            'rss_url': '',
            'error_message': error_message or ''
        }

        # Generate RSS feed if articles were found
        if success and articles:
            try:
                feed_path = self.rss_generator.create_feed(prospect, articles)
                rss_url = self.rss_generator.get_feed_url(prospect)
                tracking_entry['rss_url'] = rss_url
                print(f"   📡 Generated RSS feed: {feed_path}")
            except Exception as e:
                print(f"   ❌ Error generating RSS: {e}")
                tracking_entry['status'] = 'failed'
                tracking_entry['error_message'] = f"RSS generation error: {str(e)}"

        return tracking_entry

    def save_tracking(self):
        """Save tracking data to CSV file."""
        try:
            with open(Config.TRACKING_CSV, 'w', encoding='utf-8', newline='') as f:
                fieldnames = [
                    'prospect_id', 'company_name', 'domain', 'last_scrape_date',
                    'status', 'articles_found', 'rss_url', 'error_message'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.tracking_data)
            print(f"\n💾 Tracking data saved to {Config.TRACKING_CSV}")
        except Exception as e:
            print(f"\n❌ Error saving tracking data: {e}")

    def print_summary(self):
        """Print a summary of the scraping results."""
        total = len(self.tracking_data)
        successful = sum(1 for entry in self.tracking_data if entry['status'] == 'success')
        failed = total - successful
        total_articles = sum(entry['articles_found'] for entry in self.tracking_data)

        print("\n" + "="*60)
        print("📊 SCRAPING SUMMARY")
        print("="*60)
        print(f"Total prospects processed: {total}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📄 Total articles found: {total_articles}")
        print("="*60)

        if successful > 0:
            print("\n✅ Successfully scraped prospects:")
            for entry in self.tracking_data:
                if entry['status'] == 'success':
                    print(f"   • {entry['company_name']}: {entry['articles_found']} articles")
                    if entry['rss_url']:
                        print(f"     RSS: {entry['rss_url']}")

        if failed > 0:
            print("\n❌ Failed prospects:")
            for entry in self.tracking_data:
                if entry['status'] == 'failed':
                    print(f"   • {entry['company_name']}: {entry['error_message']}")

    def run(self):
        """Execute the complete scraping workflow."""
        print("🚀 Starting Prospect Article Scraper")
        print("="*60)

        # Load prospects
        prospects = self.load_prospects()

        if not prospects:
            print("❌ No prospects to process")
            sys.exit(1)

        # Batch processing configuration
        batch_size = int(os.getenv('BATCH_SIZE', '0'))  # 0 = process all
        max_prospects = int(os.getenv('MAX_PROSPECTS', '0'))  # 0 = no limit
        delay_between_prospects = int(os.getenv('DELAY_BETWEEN_PROSPECTS', '30'))
        
        # Apply max_prospects limit if set
        if max_prospects > 0 and len(prospects) > max_prospects:
            print(f"⚠️  Limiting to {max_prospects} prospects (loaded {len(prospects)})")
            prospects = prospects[:max_prospects]
        
        total_prospects = len(prospects)
        print(f"📊 Processing {total_prospects} prospect(s)")
        
        if batch_size > 0:
            print(f"📦 Using batch processing: {batch_size} prospects per batch")
            num_batches = (total_prospects + batch_size - 1) // batch_size
            print(f"   Will process in {num_batches} batch(es)")
        
        # Process each prospect
        for i, prospect in enumerate(prospects, 1):
            batch_num = ((i - 1) // batch_size) + 1 if batch_size > 0 else 1
            
            if batch_size > 0 and i > 1 and (i - 1) % batch_size == 0:
                print(f"\n{'='*60}")
                print(f"📦 Batch {batch_num - 1} completed. Taking a longer break before next batch...")
                print(f"{'='*60}")
                time.sleep(60)  # Longer delay between batches
            
            print(f"\n[{i}/{total_prospects}] Processing {prospect['company_name']}...")
            if batch_size > 0:
                print(f"   (Batch {batch_num}/{num_batches})")
            
            tracking_entry = self.process_prospect(prospect)
            self.tracking_data.append(tracking_entry)

            # Be nice to servers and respect Firecrawl rate limits
            if i < total_prospects:
                print(f"   ⏳ Waiting {delay_between_prospects}s before next prospect...")
                time.sleep(delay_between_prospects)

        # Save tracking data
        self.save_tracking()

        # Print summary
        self.print_summary()

        # Publish to GitHub Pages (skip if running in CI)
        is_ci = os.getenv('GITHUB_CI') == 'true'
        successful_scrapes = sum(1 for entry in self.tracking_data if entry['status'] == 'success')

        if is_ci:
            print("\n✅ Running in GitHub Actions - feeds will be committed by workflow")
        elif successful_scrapes > 0:
            print("\n📤 Publishing RSS feeds to GitHub Pages...")
            try:
                success = self.github_publisher.publish_feeds()
                if success:
                    print("✅ All feeds published successfully!")
                else:
                    print("⚠️  Some feeds may not have been published. Check the output above.")
            except Exception as e:
                print(f"❌ Error publishing feeds: {e}")
                print("\n💡 You can manually publish feeds from the 'feeds/' directory")
        else:
            print("\n⚠️  No successful scrapes to publish")

        print("\n✨ Scraping workflow completed!")


def main():
    """Main entry point."""
    scraper = ProspectScraper()
    scraper.run()


if __name__ == "__main__":
    main()
