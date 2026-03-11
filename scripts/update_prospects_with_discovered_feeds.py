#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update prospects.csv with newly discovered RSS feeds from discovery results.
"""

import csv
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from config import Config

def main():
    print("📝 Updating prospects.csv with discovered RSS feeds")
    print("=" * 80)

    # Read discovery results - index by both id and domain for flexible matching
    try:
        with open(Config.DISCOVERY_RESULTS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            discoveries_by_id = {}
            discoveries_by_domain = {}
            for row in reader:
                feed_url = row['feed_url']
                if row.get('id'):
                    discoveries_by_id[row['id']] = feed_url
                if row.get('domain'):
                    # Normalize domain for matching
                    domain = row['domain'].lower().strip()
                    discoveries_by_domain[domain] = feed_url
    except FileNotFoundError:
        print("❌ Error: rss_discovery_results_enhanced.csv not found")
        print("   Run rss_discovery_enhanced.py first to discover feeds")
        return

    print(f"📋 Loaded {len(discoveries_by_id)} discoveries by ID, {len(discoveries_by_domain)} by domain\n")

    # Read current prospects
    prospects = []
    with open(Config.PROSPECTS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        prospects = list(reader)

    # Update prospects with discovered feeds - try matching by id first, then by domain
    updated_count = 0
    for prospect in prospects:
        if prospect.get('rss_feed', '').strip():
            continue  # Already has a feed

        prospect_id = prospect['id']
        prospect_domain = prospect.get('domain', '').lower().strip()

        feed_url = None
        if prospect_id in discoveries_by_id:
            feed_url = discoveries_by_id[prospect_id]
        elif prospect_domain in discoveries_by_domain:
            feed_url = discoveries_by_domain[prospect_domain]

        if feed_url:
            prospect['rss_feed'] = feed_url
            updated_count += 1
            print(f"✅ Updated: {prospect['company_name']}")

    print(f"\n📊 Updated {updated_count} prospects with new RSS feeds")

    # Write updated prospects.csv
    with open(Config.PROSPECTS_CSV, 'w', encoding='utf-8', newline='') as f:
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
