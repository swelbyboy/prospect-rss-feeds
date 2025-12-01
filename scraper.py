#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main RSS feed transformer orchestrator.
Transforms original RSS feeds to GitHub Pages feeds for prospects.
"""

import csv
import os
import sys
import time
from datetime import datetime
from config import Config
from rss_generator import RSSFeedGenerator
from github_publisher import GitHubPublisher
from rss_transformer import RSSTransformer


class ProspectScraper:
    """Main orchestrator for transforming prospect RSS feeds to GitHub Pages."""

    def __init__(self):
        """Initialize the transformer with required components."""
        try:
            Config.validate()
        except ValueError as e:
            print(f"❌ Configuration error: {e}")
            sys.exit(1)

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

            # Filter prospects based on RSS feed availability and status
            original_count = len(prospects)
            
            # Only process prospects that have original RSS feeds (not "-" or swelbyboy.github.io)
            filtered_prospects = []
            skipped_no_feed = 0
            skipped_already_processed = 0
            
            for p in prospects:
                rss_feed = p.get('rss_feed', '').strip()
                
                # Skip if no RSS feed or placeholder
                if not rss_feed or rss_feed == '-':
                    skipped_no_feed += 1
                    continue
                
                # Skip if already a GitHub Pages feed (already processed)
                if 'swelbyboy.github.io' in rss_feed:
                    skipped_already_processed += 1
                    continue
                
                # This has an original RSS feed that needs transformation
                filtered_prospects.append(p)
            
            print(f"✅ Skipping {skipped_no_feed} prospects with no RSS feed")
            print(f"✅ Skipping {skipped_already_processed} prospects already processed")
            print(f"📊 Found {len(filtered_prospects)} prospects with original RSS feeds to transform")

            return filtered_prospects
        except FileNotFoundError:
            print(f"❌ Prospects file not found: {Config.PROSPECTS_CSV}")
            print("Please create a prospects.csv file with columns: id, company_name, domain")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error loading prospects: {e}")
            sys.exit(1)

    def scrape_articles(self, prospect):
        """
        Transform articles from prospect's original RSS feed.

        Strategy:
        1. Fetch content from original RSS feed
        2. Transform and normalize the content
        3. No web scraping - RSS feed required

        Args:
            prospect (dict): Prospect information

        Returns:
            tuple: (success: bool, articles: list, error_message: str)
        """
        domain = prospect['domain']
        company_name = prospect['company_name']
        rss_feed = prospect.get('rss_feed', '').strip()

        print(f"\n🔍 Processing {company_name} ({domain})...")

        # Validate RSS feed is present and not a placeholder
        if not rss_feed or rss_feed == '-':
            print(f"   ⚠️  No RSS feed available - skipping")
            return False, [], "No RSS feed available"
        
        # Skip if already processed (GitHub Pages feed)
        if 'swelbyboy.github.io' in rss_feed:
            print(f"   ✅ Already processed - using GitHub Pages feed")
            # Still fetch to regenerate the feed
            success, articles, error = self.rss_transformer.fetch_and_normalize(
                rss_feed,
                max_articles=Config.MAX_ARTICLES_PER_PROSPECT
            )
            
            if success:
                normalized_articles = []
                for article in articles:
                    normalized_articles.append({
                        'link': article['link'],
                        'title': article['title'],
                        'description': article['description'],
                        'image_url': article.get('image_url'),
                        'published_date': article['pub_date']
                    })
                return True, normalized_articles, None
            else:
                return False, [], error

        # Process original RSS feed
        print(f"   📡 Transforming original RSS feed: {rss_feed}")
        success, articles, error = self.rss_transformer.fetch_and_normalize(
            rss_feed,
            max_articles=Config.MAX_ARTICLES_PER_PROSPECT
        )

        if success:
            # Convert RSS articles to our format
            normalized_articles = []
            for article in articles:
                normalized_articles.append({
                    'link': article['link'],
                    'title': article['title'],
                    'description': article['description'],
                    'image_url': article.get('image_url'),
                    'published_date': article['pub_date']
                })
            print(f"   ✅ Successfully transformed {len(normalized_articles)} articles")
            return True, normalized_articles, None
        else:
            print(f"   ❌ RSS transformation failed: {error}")
            return False, [], error

    # Firecrawl scraping methods removed - we only use RSS feeds now

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

    def update_prospect_csv(self):
        """Update the original prospects CSV with GitHub Pages URLs and status."""
        try:
            # Read all prospects from CSV
            all_prospects = []
            with open(Config.PROSPECTS_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                all_prospects = list(reader)
            
            # Update prospects that were processed
            updates_made = 0
            for entry in self.tracking_data:
                for prospect in all_prospects:
                    # Match by domain or company name
                    prospect_name = prospect.get('Prospect Name', prospect.get('company_name', ''))
                    prospect_domain = prospect.get('Domain', prospect.get('domain', ''))
                    
                    if (prospect_name == entry['company_name'] or 
                        prospect_domain == entry['domain']):
                        # Update RSS Feed column
                        if entry['status'] == 'success' and entry['rss_url']:
                            if 'RSS Feed' in prospect:
                                prospect['RSS Feed'] = entry['rss_url']
                            elif 'rss_feed' in prospect:
                                prospect['rss_feed'] = entry['rss_url']
                            
                            # Update Last Scrape Status
                            if 'Last Scrape Status' in prospect:
                                prospect['Last Scrape Status'] = 'success'
                            
                            # Update Last Scrape Timestamp
                            if 'Last Scrape Timestamp' in prospect:
                                prospect['Last Scrape Timestamp'] = entry['last_scrape_date']
                            
                            # Update Data Source
                            if 'Data Source' in prospect:
                                prospect['Data Source'] = 'OG'
                            
                            # Update Status to "To Do" for successful transformations
                            if 'Status' in prospect:
                                prospect['Status'] = 'To Do'
                            
                            updates_made += 1
                        elif entry['status'] == 'failed':
                            # Update Last Scrape Status to failed
                            if 'Last Scrape Status' in prospect:
                                prospect['Last Scrape Status'] = 'failed'
                            
                            if 'Last Scrape Timestamp' in prospect:
                                prospect['Last Scrape Timestamp'] = entry['last_scrape_date']
                        break
            
            # Write updated data back to CSV
            with open(Config.PROSPECTS_CSV, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_prospects)
            
            print(f"\n💾 Updated {updates_made} prospects in {Config.PROSPECTS_CSV}")
            
        except Exception as e:
            print(f"\n❌ Error updating prospect CSV: {e}")

    def print_summary(self):
        """Print a summary of the transformation results."""
        total = len(self.tracking_data)
        successful = sum(1 for entry in self.tracking_data if entry['status'] == 'success')
        failed = total - successful
        total_articles = sum(entry['articles_found'] for entry in self.tracking_data)

        print("\n" + "="*60)
        print("📊 TRANSFORMATION SUMMARY")
        print("="*60)
        print(f"Total prospects processed: {total}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📄 Total articles transformed: {total_articles}")
        print("="*60)

        if successful > 0:
            print("\n✅ Successfully transformed prospects:")
            for entry in self.tracking_data:
                if entry['status'] == 'success':
                    print(f"   • {entry['company_name']}: {entry['articles_found']} articles")
                    if entry['rss_url']:
                        print(f"     GitHub Pages: {entry['rss_url']}")

        if failed > 0:
            print("\n❌ Failed prospects:")
            for entry in self.tracking_data:
                if entry['status'] == 'failed':
                    print(f"   • {entry['company_name']}: {entry['error_message']}")

    def run(self):
        """Execute the complete RSS feed transformation workflow."""
        print("🚀 Starting RSS Feed Transformer")
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
        
        # Update the original prospects CSV with GitHub Pages URLs
        self.update_prospect_csv()

        # Print summary
        self.print_summary()

        # Publish to GitHub Pages (skip if running in CI)
        is_ci = os.getenv('GITHUB_CI') == 'true'
        successful_transforms = sum(1 for entry in self.tracking_data if entry['status'] == 'success')

        if is_ci:
            print("\n✅ Running in GitHub Actions - feeds will be committed by workflow")
        elif successful_transforms > 0:
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
            print("\n⚠️  No successful transformations to publish")

        print("\n✨ RSS feed transformation workflow completed!")


def main():
    """Main entry point."""
    scraper = ProspectScraper()
    scraper.run()


if __name__ == "__main__":
    main()
