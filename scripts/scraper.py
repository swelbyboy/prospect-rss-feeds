#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main RSS feed transformer orchestrator.
Transforms original RSS feeds to GitHub Pages feeds for prospects.
"""

import asyncio
import aiohttp
import csv
import os
import sys
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import ctypes
import gc
import signal
from config import Config
from rss_generator import RSSFeedGenerator
from github_publisher import GitHubPublisher
from rss_transformer import RSSTransformer

# Global for graceful shutdown
should_exit = False

# For releasing memory back to OS after gc.collect()
try:
    _libc = ctypes.CDLL("libc.so.6")
except Exception:
    _libc = None

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    global should_exit
    print('\n\n⚠️  Interrupt received. Finishing current tasks and saving...')
    should_exit = True

signal.signal(signal.SIGINT, signal_handler)


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
        self.completed_count = 0

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

                # Handle domain / Domain (resolve first, used as fallback for company_name)
                if 'domain' in prospect:
                    normalized['domain'] = prospect['domain']
                elif 'Domain' in prospect:
                    normalized['domain'] = prospect['Domain']
                else:
                    normalized['domain'] = ''

                # Handle company_name / Prospect Name; fall back to domain
                if 'company_name' in prospect:
                    normalized['company_name'] = prospect['company_name'] or normalized['domain']
                elif 'Prospect Name' in prospect:
                    normalized['company_name'] = prospect['Prospect Name'] or normalized['domain']
                else:
                    normalized['company_name'] = normalized['domain'] or f"Unknown-{i}"

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
            
            # Load original feed URLs from discovery results (for regenerating missing feeds)
            original_feeds = {}
            try:
                with open(Config.DISCOVERY_RESULTS_CSV, 'r', encoding='utf-8') as f:
                    import csv as csv_module
                    reader = csv_module.DictReader(f)
                    for row in reader:
                        domain = row.get('domain', '')
                        feed_url = row.get('feed_url', '')
                        if domain and feed_url:
                            original_feeds[domain] = feed_url
                print(f"📋 Loaded {len(original_feeds)} original feed URLs for regeneration")
            except Exception as e:
                print(f"⚠️  Could not load discovery results: {e}")
            
            # Process prospects - including those with missing XML files
            filtered_prospects = []
            skipped_no_feed = 0
            skipped_already_processed = 0
            needs_regeneration = 0
            
            for p in prospects:
                rss_feed = p.get('rss_feed', '').strip()
                domain = p.get('domain', '')
                
                # Skip if no RSS feed or placeholder
                if not rss_feed or rss_feed == '-':
                    skipped_no_feed += 1
                    continue
                
                # Check if already a GitHub Pages feed
                if 'swelbyboy.github.io' in rss_feed:
                    # Extract filename and check if XML actually exists
                    filename = rss_feed.split('/')[-1]
                    xml_path = os.path.join(Config.FEEDS_DIR, filename)
                    
                    if os.path.exists(xml_path):
                        # XML exists - truly already processed
                        skipped_already_processed += 1
                        continue
                    else:
                        # XML missing! Look up original feed URL
                        original_url = original_feeds.get(domain, '')
                        if original_url:
                            # Replace with original URL for regeneration
                            p['rss_feed'] = original_url
                            needs_regeneration += 1
                            filtered_prospects.append(p)
                        else:
                            # No original URL found - can't regenerate
                            skipped_no_feed += 1
                        continue
                
                # This has an original RSS feed that needs transformation
                filtered_prospects.append(p)
            
            print(f"✅ Skipping {skipped_no_feed} prospects with no RSS feed")
            print(f"✅ Skipping {skipped_already_processed} prospects already processed (XML exists)")
            if needs_regeneration > 0:
                print(f"🔄 Regenerating {needs_regeneration} feeds with missing XML files")
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
        rss_feed = prospect.get('rss_feed', '').strip()

        # Validate RSS feed is present and not a placeholder
        if not rss_feed or rss_feed == '-':
            return False, [], "No RSS feed available"
        
        # Skip if already processed (GitHub Pages feed)
        if 'swelbyboy.github.io' in rss_feed:
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
            return True, normalized_articles, None
        else:
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
        """Merge current run results into tracking.csv, updating existing rows by domain."""
        fieldnames = [
            'prospect_id', 'company_name', 'domain', 'last_scrape_date',
            'status', 'articles_found', 'rss_url', 'error_message'
        ]
        try:
            # Load existing tracking data keyed by domain
            existing = {}
            if os.path.exists(Config.TRACKING_CSV):
                with open(Config.TRACKING_CSV, 'r', encoding='utf-8') as f:
                    for row in csv.DictReader(f):
                        d = row.get('domain', '')
                        if d:
                            existing[d] = row

            # Overwrite with current run results
            for entry in self.tracking_data:
                existing[entry.get('domain', '')] = entry

            with open(Config.TRACKING_CSV, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(existing.values())
            print(f"\n💾 Tracking data saved ({len(existing)} total entries)")
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

    def process_prospect_parallel(self, prospect, index, total, print_lock):
        """
        Process a single prospect in parallel (thread-safe).
        
        Args:
            prospect: Prospect dictionary
            index: Current index for progress display
            total: Total number of prospects
            print_lock: Threading lock for print statements
            
        Returns:
            dict: Tracking entry for this prospect
        """
        global should_exit
        if should_exit:
            return None
            
        company_name = prospect['company_name']
        domain = prospect['domain']
        
        with print_lock:
            print(f"\n[{index}/{total}] Processing {company_name} ({domain})...")
        
        # Process the prospect
        tracking_entry = self.process_prospect(prospect)
        
        with print_lock:
            if tracking_entry['status'] == 'success':
                print(f"   ✅ {company_name}: {tracking_entry['articles_found']} articles → {tracking_entry['rss_url']}")
            else:
                print(f"   ❌ {company_name}: {tracking_entry['error_message']}")
        
        gc.collect()
        if _libc:
            _libc.malloc_trim(0)
        return tracking_entry

    async def process_prospect_async(self, prospect, index, total, semaphore, session):
        async with semaphore:
            feed_url = prospect.get('rss_feed', '')
            tracking_entry = {
                'prospect_id': prospect.get('id', ''),
                'company_name': prospect.get('company_name', ''),
                'domain': prospect.get('domain', ''),
                'last_scrape_date': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'failed',
                'articles_found': 0,
                'rss_url': '',
                'error_message': '',
            }
            try:
                success, articles, error = await self.rss_transformer.async_fetch_and_normalize(
                    session, feed_url, max_articles=Config.MAX_ARTICLES_PER_PROSPECT
                )
                if success and articles:
                    # create_feed reads/writes local XML files — run in thread
                    feed_path = await asyncio.to_thread(
                        self.rss_generator.create_feed, prospect, articles
                    )
                    tracking_entry['status'] = 'success'
                    tracking_entry['articles_found'] = len(articles)
                    tracking_entry['rss_url'] = self.rss_generator.get_feed_url(prospect)
                else:
                    tracking_entry['error_message'] = error or 'No articles'
            except Exception as e:
                tracking_entry['error_message'] = str(e)

            self.tracking_data.append(tracking_entry)
            self.completed_count += 1

            if self.completed_count % 25 == 0:
                await asyncio.to_thread(self.save_tracking)

            if self.completed_count % 50 == 0 or self.completed_count == total:
                print(f"Progress: {self.completed_count}/{total}")

            return tracking_entry

    async def run_async(self):
        prospects = self.load_prospects()
        if not prospects:
            print("No prospects to process.")
            return

        total = len(prospects)
        concurrency = int(os.getenv('PARALLEL_WORKERS', '50'))
        print(f"Processing {total} prospects with concurrency={concurrency}")

        semaphore = asyncio.Semaphore(concurrency)
        connector = aiohttp.TCPConnector(limit=concurrency + 10, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=15, connect=5)
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; RSSTransformer/1.0)'}

        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout, headers=headers
        ) as session:
            tasks = [
                self.process_prospect_async(p, i + 1, total, semaphore, session)
                for i, p in enumerate(prospects)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        self.save_tracking()
        self.update_prospect_csv()
        self.print_summary()

    def run(self):
        """Execute the complete RSS feed transformation workflow."""
        asyncio.run(self.run_async())


def main():
    """Main entry point."""
    scraper = ProspectScraper()
    scraper.run()


if __name__ == "__main__":
    main()
