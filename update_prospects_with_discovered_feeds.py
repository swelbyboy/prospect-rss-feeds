#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update prospects.csv with newly discovered RSS feeds from discovery results.
"""

import csv

def main():
    print("📝 Updating prospects.csv with discovered RSS feeds")
    print("=" * 80)

    # Read discovery results
    try:
        with open('rss_discovery_results_enhanced.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            discoveries = {row['id']: row['feed_url'] for row in reader}
    except FileNotFoundError:
        print("❌ Error: rss_discovery_results_enhanced.csv not found")
        print("   Run rss_discovery_enhanced.py first to discover feeds")
        return

    print(f"📋 Loaded {len(discoveries)} discovered feeds\n")

    # Read current prospects
    prospects = []
    with open('prospects.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        prospects = list(reader)

    # Update prospects with discovered feeds
    updated_count = 0
    for prospect in prospects:
        prospect_id = prospect['id']
        if prospect_id in discoveries and not prospect.get('rss_feed', '').strip():
            prospect['rss_feed'] = discoveries[prospect_id]
            updated_count += 1
            print(f"✅ Updated: {prospect['company_name']}")

    print(f"\n📊 Updated {updated_count} prospects with new RSS feeds")

    # Write updated prospects.csv
    with open('prospects.csv', 'w', encoding='utf-8', newline='') as f:
        fieldnames = prospects[0].keys() if prospects else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(prospects)

    print(f"✅ Saved updated prospects.csv")

    # Count totals
    with_feeds = sum(1 for p in prospects if p.get('rss_feed', '').strip())
    total = len(prospects)

    print(f"\n📈 Summary:")
    print(f"   Total prospects: {total}")
    print(f"   With RSS feeds: {with_feeds} ({with_feeds/total*100:.1f}%)")
    print(f"   Without RSS feeds: {total - with_feeds} ({(total-with_feeds)/total*100:.1f}%)")

if __name__ == '__main__':
    main()
