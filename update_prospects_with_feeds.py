#!/usr/bin/env python3
"""
Update Prospects with Discovered RSS Feeds
Merges discovered RSS feed URLs from rss_discovery_results.csv into prospects.csv
"""

import csv

def main():
    print("🔄 Updating prospects.csv with discovered RSS feeds")
    print("=" * 80)

    # Read discovered feeds
    discovered_feeds = {}
    with open('rss_discovery_results.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prospect_id = row['id']
            discovered_feeds[prospect_id] = row['feed_url']

    print(f"📥 Loaded {len(discovered_feeds)} discovered RSS feeds")

    # Read and update prospects
    prospects = []
    updated_count = 0

    with open('prospects.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        for row in reader:
            prospect_id = row['id']

            # Update RSS feed if discovered
            if prospect_id in discovered_feeds:
                if not row.get('rss_feed', '').strip():
                    row['rss_feed'] = discovered_feeds[prospect_id]
                    updated_count += 1
                    print(f"  ✅ Updated {row['company_name']} ({row['domain']}) -> {discovered_feeds[prospect_id]}")

            prospects.append(row)

    # Write updated prospects back
    with open('prospects.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(prospects)

    print("\n" + "=" * 80)
    print("📊 UPDATE SUMMARY")
    print("=" * 80)
    print(f"Total prospects: {len(prospects)}")
    print(f"✅ RSS feeds added: {updated_count}")
    print("=" * 80)
    print(f"\n✅ Updated prospects.csv with {updated_count} new RSS feeds")

    # Count final stats
    with_feeds = sum(1 for p in prospects if p.get('rss_feed', '').strip())
    without_feeds = len(prospects) - with_feeds

    print(f"\nFinal status:")
    print(f"  • Prospects with RSS feeds: {with_feeds}")
    print(f"  • Prospects without RSS feeds: {without_feeds}")

if __name__ == '__main__':
    main()
