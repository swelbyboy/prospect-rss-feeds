#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSS Publisher
Simplified workflow that fetches RSS feeds, normalizes them, and publishes to GitHub Pages.
"""

import csv
import sys
from rss_transformer import RSSTransformer
from rss_generator import RSSFeedGenerator
from github_publisher import GitHubPublisher
from config import Config


class RSSPublisher:
    """Fetches RSS feeds and publishes them to GitHub Pages."""

    def __init__(self):
        """Initialize the RSS publisher."""
        try:
            Config.validate()
        except ValueError as e:
            print(f"❌ Configuration error: {e}")
            sys.exit(1)

        self.rss_transformer = RSSTransformer()
        self.rss_generator = RSSFeedGenerator()
        self.github_publisher = GitHubPublisher()

    def load_rss_prospects(self, csv_path):
        """
        Load prospects that have RSS feeds.

        Args:
            csv_path (str): Path to prospects CSV

        Returns:
            list: Prospects with RSS feeds
        """
        prospects = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('rss_feed', '').strip():
                        prospects.append(row)

            print(f"📋 Loaded {len(prospects)} prospects with RSS feeds from {csv_path}")
            return prospects

        except FileNotFoundError:
            print(f"❌ File not found: {csv_path}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error loading prospects: {e}")
            sys.exit(1)

    def process_prospect(self, prospect, max_articles):
        """
        Process a single prospect's RSS feed.

        Args:
            prospect (dict): Prospect data
            max_articles (int): Max articles to fetch

        Returns:
            tuple: (success: bool, feed_path: str, error: str, data_source: str)
        """
        company_name = prospect.get('company_name', 'Unknown')
        domain = prospect.get('domain', '')
        rss_feed = prospect.get('rss_feed', '').strip()

        print(f"\n📡 Processing {company_name} ({domain})...")

        # Fetch and normalize RSS feed
        success, articles, error = self.rss_transformer.fetch_and_normalize(
            rss_feed,
            max_articles=max_articles
        )

        if not success:
            print(f"   ❌ Failed: {error}")
            return False, None, error, None

        print(f"   ✅ Fetched {len(articles)} articles")

        # Determine data source (OG or RSS) - use the first article's data source
        data_source = articles[0].get('data_source', 'RSS') if articles else 'RSS'

        # Count how many articles used OG vs RSS
        og_count = sum(1 for a in articles if a.get('data_source') == 'OG')
        rss_count = len(articles) - og_count

        if og_count > 0 and rss_count > 0:
            data_source = f"OG ({og_count}), RSS ({rss_count})"
        elif og_count > 0:
            data_source = "OG"
        else:
            data_source = "RSS"

        print(f"   📊 Data sources: {data_source}")

        # Convert to format expected by RSS generator
        normalized_articles = []
        for article in articles:
            normalized_articles.append({
                'link': article['link'],
                'title': article['title'],
                'description': article['description'],
                'image_url': article.get('image_url'),
                'published_date': article['pub_date']
            })

        # Generate RSS feed
        try:
            prospect_data = {
                'id': prospect.get('id'),
                'company_name': company_name,
                'domain': domain
            }
            feed_path = self.rss_generator.create_feed(prospect_data, normalized_articles)
            print(f"   📄 Generated feed: {feed_path}")
            return True, feed_path, None, data_source

        except Exception as e:
            print(f"   ❌ Error generating feed: {e}")
            return False, None, str(e), None

    def run(self, prospects_csv, max_articles=10):
        """
        Main workflow: fetch RSS feeds and publish to GitHub Pages.

        Args:
            prospects_csv (str): Path to prospects CSV
            max_articles (int): Max articles per prospect
        """
        print("🚀 Starting RSS Publisher")
        print("=" * 80)

        # Load RSS prospects
        prospects = self.load_rss_prospects(prospects_csv)

        if not prospects:
            print("❌ No prospects with RSS feeds found!")
            sys.exit(1)

        print(f"📊 Processing {len(prospects)} prospect(s) with RSS feeds\n")

        # Process each prospect
        successful = 0
        failed = 0
        failed_prospects = []

        for i, prospect in enumerate(prospects, 1):
            company_name = prospect.get('company_name', 'Unknown')
            print(f"[{i}/{len(prospects)}] {company_name}")

            success, feed_path, error, data_source = self.process_prospect(prospect, max_articles)

            if success:
                successful += 1
            else:
                failed += 1
                failed_prospects.append({
                    'name': company_name,
                    'error': error
                })

        # Summary
        print("\n" + "=" * 80)
        print("📊 PROCESSING SUMMARY")
        print("=" * 80)
        print(f"Total prospects processed: {len(prospects)}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print("=" * 80)

        if failed_prospects:
            print("\n❌ Failed prospects:")
            for fp in failed_prospects:
                print(f"   • {fp['name']}: {fp['error']}")

        if successful == 0:
            print("\n⚠️  No successful feeds to publish")
            sys.exit(1)

        # Publish to GitHub Pages
        print(f"\n📤 Publishing {successful} RSS feeds to GitHub Pages...")
        try:
            self.github_publisher.publish_feeds()
            print("✅ All feeds published successfully!")
        except Exception as e:
            print(f"❌ Error publishing to GitHub: {e}")
            sys.exit(1)

        print("\n✨ RSS publishing completed!")


def main():
    """Main entry point."""
    import os

    prospects_csv = os.environ.get('PROSPECTS_CSV', 'prospects.csv')
    max_articles = int(os.environ.get('MAX_ARTICLES_PER_PROSPECT', '10'))

    publisher = RSSPublisher()
    publisher.run(prospects_csv, max_articles)


if __name__ == "__main__":
    main()
