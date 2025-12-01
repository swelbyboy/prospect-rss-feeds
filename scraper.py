#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
from rss_transformer import RSSTransformer


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
        self.rss_transformer = RSSTransformer()
        self.tracking_data = []

    def load_prospects(self):
        """
        Load prospects from CSV file, optionally skipping already-processed ones.

        Returns:
            list: List of prospect dictionaries
        """
        prospects = []
        try:
            with open(Config.PROSPECTS_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                prospects = list(reader)
            print(f"📋 Loaded {len(prospects)} prospects from {Config.PROSPECTS_CSV}")

            # Normalize column names to handle different CSV formats
            # outreach_progress_tracker.csv uses: "Prospect Name", "Domain", "RSS Feed"
            # prospects.csv uses: "company_name", "domain", "rss_feed"
            normalized_prospects = []
            for i, prospect in enumerate(prospects, 1):
                normalized = {}

                # Handle company_name / Prospect Name
                if 'company_name' in prospect:
                    normalized['company_name'] = prospect['company_name']
                elif 'Prospect Name' in prospect:
                    normalized['company_name'] = prospect['Prospect Name']
                else:
                    normalized['company_name'] = f"Unknown-{i}"

                # Handle domain / Domain
                if 'domain' in prospect:
                    normalized['domain'] = prospect['domain']
                elif 'Domain' in prospect:
                    normalized['domain'] = prospect['Domain']
                else:
                    normalized['domain'] = ''

                # Handle rss_feed / RSS Feed
                if 'rss_feed' in prospect:
                    normalized['rss_feed'] = prospect['rss_feed']
                elif 'RSS Feed' in prospect:
                    normalized['rss_feed'] = prospect['RSS Feed']
                else:
                    normalized['rss_feed'] = ''

                # Handle id (generate if not present)
                if 'id' in prospect:
                    normalized['id'] = prospect['id']
                else:
                    normalized['id'] = str(i)

                normalized_prospects.append(normalized)

            prospects = normalized_prospects

            # Check if we should skip already-processed prospects
            skip_processed = os.getenv('SKIP_PROCESSED', 'true').lower() == 'true'

            if skip_processed and os.path.exists(Config.TRACKING_CSV):
                # Load already-processed prospect IDs
                processed_ids = set()
                try:
                    with open(Config.TRACKING_CSV, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row.get('status') == 'success':
                                processed_ids.add(row.get('prospect_id', ''))

                    if processed_ids:
                        original_count = len(prospects)
                        prospects = [p for p in prospects if p.get('id', '') not in processed_ids]
                        skipped = original_count - len(prospects)
                        print(f"✅ Skipping {skipped} already-processed prospects")
                        print(f"📊 Remaining prospects to process: {len(prospects)}")
                except Exception as e:
                    print(f"⚠️  Could not load tracking data: {e}")

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
        Scrape articles from a prospect's website.

        Strategy:
        1. Try RSS feed first if available (faster, cleaner)
        2. Fall back to Firecrawl web scraping if no RSS or RSS fails

        Args:
            prospect (dict): Prospect information

        Returns:
            tuple: (success: bool, articles: list, error_message: str)
        """
        domain = prospect['domain']
        company_name = prospect['company_name']
        rss_feed = prospect.get('rss_feed', '').strip()

        print(f"\n🔍 Scraping {company_name} ({domain})...")

        # Try RSS first if available
        if rss_feed:
            print(f"   📡 Using RSS feed: {rss_feed}")
            success, articles, error = self.rss_transformer.fetch_and_normalize(
                rss_feed,
                max_articles=Config.MAX_ARTICLES_PER_PROSPECT
            )

            if success:
                # Convert RSS articles to our format
                normalized_articles = []
                for article in articles:
                    normalized_articles.append({
                        'link': article['link'],  # RSS generator expects 'link', not 'url'
                        'title': article['title'],
                        'description': article['description'],
                        'image_url': article.get('image_url'),
                        'published_date': article['pub_date']
                    })
                return True, normalized_articles, None
            else:
                print(f"   ⚠️  RSS fetch failed: {error}, falling back to web scraping...")

        # Fall back to web scraping
        return self._scrape_with_firecrawl(prospect)

    def _scrape_with_firecrawl(self, prospect):
        """
        Scrape articles using Firecrawl (original method).

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

        print(f"   🌐 Using web scraping (Firecrawl)...")

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

            # Retry with exponential backoff for transient errors
            max_retries = 3
            retry_delay = 10
            homepage_result = None
            retryable_errors = ['408', '502', '500', 'timeout', 'server login']

            for attempt in range(max_retries):
                try:
                    homepage_result = self.firecrawl.scrape_url(url, params=homepage_params)
                    break  # Success!
                except Exception as e:
                    error_str = str(e).lower()
                    is_retryable = any(err in error_str for err in retryable_errors)

                    if is_retryable and attempt < max_retries - 1:
                        print(f"   ⏳ Transient error, waiting {retry_delay}s before retry {attempt + 2}/{max_retries}...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        raise  # Re-raise if not retryable or final attempt

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
            retryable_errors = ['408', '502', '500', 'timeout', 'server login']

            for idx, article_url in enumerate(article_urls, 1):
                print(f"   📖 Scraping article {idx}/{len(article_urls)}...")

                # Retry logic for individual articles
                article_result = None
                max_article_retries = 2  # Fewer retries per article
                article_retry_delay = 5

                for attempt in range(max_article_retries):
                    try:
                        article_result = self.firecrawl.scrape_url(
                            article_url,
                            params={'formats': ['markdown']}
                        )
                        break  # Success!
                    except Exception as e:
                        error_str = str(e).lower()
                        is_retryable = any(err in error_str for err in retryable_errors)

                        if is_retryable and attempt < max_article_retries - 1:
                            print(f"   ⏳ Retrying article after {article_retry_delay}s...")
                            time.sleep(article_retry_delay)
                        elif attempt == max_article_retries - 1:
                            print(f"   ⚠️  Failed to scrape article {idx}: {str(e)}")

                if article_result:
                    try:
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
                    except Exception as e:
                        print(f"   ⚠️  Error processing article {idx}: {str(e)}")
                        continue

                # Small delay to be nice to Firecrawl API
                time.sleep(1)

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
            '/disclaimer', '/advertise', '/advertising', '/editorial',
            '/masthead', '/staff', '/team',
            # Administrative
            '/tag/', '/category/', '/author/', '/page/', '/community/',
            '/feed', '/rss', '/api/', '/wp-admin', '/wp-content',
            # Affiliate/commercial
            '/out/', '/deals/', '/shop/', '/buy/', '/product/',
            # Media/content types (match with or without trailing slash)
            '/podcast', '/video/', '/videos/', '/gallery/', '/galleries/', '/photos/',
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

        Strategy: Prioritize metadata signals over content heuristics for robust detection.

        Args:
            metadata (dict): Article metadata from Firecrawl
            markdown_content (str): Article markdown content
            url (str): Article URL

        Returns:
            bool: True if valid article, False otherwise
        """
        # Get title and description
        raw_title = metadata.get('title', '')
        title_lower = raw_title.lower()
        description = metadata.get('description', '')
        url_lower = url.lower()

        # === CRITICAL FILTERS - Always reject these ===

        # 0. HOMEPAGE DETECTION
        url_clean = url_lower.replace('https://', '').replace('http://', '').replace('www.', '').rstrip('/')
        if '/' not in url_clean:
            return False

        # 1. OBVIOUS NON-ARTICLES BY URL
        obvious_non_article_urls = [
            '/about', '/contact', '/privacy', '/terms', '/login', '/signup',
            '/subscribe', '/newsletter', '/advertise', '/careers', '/jobs',
            '/listen', '/schedule', '/on-air', '/calendar', '/events',
            '/podcast', '/video/', '/videos/', '/gallery/', '/galleries/',
            '/editorial', '/masthead', '/staff', '/team',
            '/out/', '/deals/', '/shop/', '/buy/', '/product/'
        ]
        if any(pattern in url_lower for pattern in obvious_non_article_urls):
            return False

        # 2. OBVIOUS NON-ARTICLES BY TITLE
        non_article_title_patterns = [
            'home', 'homepage', 'listen live', 'contact us', 'about us',
            'privacy policy', 'terms', 'subscribe', 'newsletter',
            'advertise', 'careers', 'jobs', '404', 'not found',
            'search results for', 'editorial guidelines', 'editorial policy',
            'crime stories with nancy grace', 'podcast'
        ]
        if any(pattern in title_lower for pattern in non_article_title_patterns):
            return False

        # 3. EVERGREEN/BUYING GUIDE PATTERNS (even with good metadata)
        evergreen_patterns = [
            'best ', 'top ', ' in 202', ' guide', 'how to ',
            'a brief history of', 'history of ', 'ultimate guide',
            'complete guide', 'beginner\'s guide'
        ]
        for pattern in evergreen_patterns:
            if pattern in title_lower:
                # Additional check: if it's a "best" or "top" list AND has a year, likely evergreen
                if ('best ' in title_lower or 'top ' in title_lower) and any(year in title_lower for year in ['2024', '2025', '2026']):
                    return False
                # "How to" guides, history articles
                if pattern in ['how to ', 'a brief history of', 'history of ', 'complete guide', 'ultimate guide']:
                    return False

        # === METADATA VALIDATION - Trust structured data first ===

        # Check for article metadata signals
        has_published_date = bool(metadata.get('publishedTime') or metadata.get('published') or metadata.get('datePublished'))
        has_og_type = metadata.get('ogType', '').lower() in ['article', 'blog', 'news']
        has_description = len(description) > 30
        metadata_score = 0
        if has_og_type:
            metadata_score += 2
        if has_published_date:
            metadata_score += 2
        if has_description:
            metadata_score += 1

        # === URL PATTERN ANALYSIS - Articles have specific patterns ===

        # Check for date in URL (e.g., /2025/11/09/ or /2025-11-09/)
        import re
        date_pattern = r'/(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12][0-9]|3[01])'
        if re.search(date_pattern, url_lower):
            # URLs with dates are almost always articles
            return True

        # Multi-segment URLs (3+ parts) are likely articles
        url_path = url_lower.split('?')[0]
        if '://' in url_path:
            url_path = url_path.split('://', 1)[1]
        if '/' in url_path:
            url_path = url_path.split('/', 1)[1]

        path_parts = [p for p in url_path.strip('/').split('/') if p]

        # Single-segment URLs are usually category pages
        if len(path_parts) == 1:
            section_names = ['news', 'blog', 'sports', 'tech', 'business', 'entertainment',
                           'politics', 'science', 'health', 'world', 'local', 'opinion', 'editorial']
            if path_parts[0] in section_names or len(path_parts[0]) < 15:
                return False
            slug_tokens = [token for token in path_parts[0].split('-') if token]
            category_tokens = {
                'guide', 'guides', 'history', 'faq', 'faqs', 'glossary', 'dictionary',
                'appliances', 'software', 'services', 'products', 'pricing', 'deals',
                'coupons', 'store', 'shop', 'support', 'help', 'download', 'downloads',
                'resources'
            }
            if slug_tokens and any(token in category_tokens for token in slug_tokens):
                if len(slug_tokens) <= 2:
                    return False

        # === CONTENT HEURISTICS - Fallback validation ===

        # Basic title quality
        if len(raw_title.strip()) < 10 or len(title_lower.split()) < 3:
            return False

        # Get word count
        content_words = markdown_content.split() if markdown_content else []
        word_count = len(content_words)

        # Minimum content length
        if word_count < 75:  # Reduced to allow shorter news articles
            return False

        # Check link density
        if markdown_content and word_count > 0:
            link_count = markdown_content.count('](')
            links_per_100_words = (link_count / word_count) * 100
            if links_per_100_words > 30:
                return False

        # Content quality checks with lower thresholds since we don't have metadata

        # With description + reasonable content
        if has_description and word_count >= 100:
            return True

        # Substantial content even without metadata
        if word_count >= 200:
            return True

        if metadata_score >= 4 and word_count >= 70:
            return True

        if metadata_score >= 3 and len(path_parts) >= 2 and word_count >= 70:
            return True

        # Multi-segment URL + some content + title
        if len(path_parts) >= 2 and word_count >= 75 and len(raw_title) >= 20:
            return True

        if metadata_score >= 2 and word_count >= 120:
            return True

        # Not enough signals to confidently identify as article
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
