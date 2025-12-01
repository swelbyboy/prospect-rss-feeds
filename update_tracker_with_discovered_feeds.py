#!/usr/bin/env python3
"""
Update the progress tracker with RSS feeds from rss_discovery_results_enhanced.csv
"""

import csv
from datetime import datetime

def update_tracker():
    # Read rss_discovery_results
    print("📋 Loading rss_discovery_results_enhanced.csv...")
    discovered_feeds = {}
    discovery_methods = {}

    with open('rss_discovery_results_enhanced.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row['domain']
            discovered_feeds[domain] = row['feed_url']
            discovery_methods[domain] = row['discovery_method']

    print(f"✅ Loaded {len(discovered_feeds)} discovered feeds")

    # Read the tracker
    tracker_file = 'Newsletter outreach #2 - Progress tracker - UPDATED.csv'
    print(f"\n📋 Loading {tracker_file}...")

    rows = []
    with open(tracker_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"✅ Loaded {len(rows)} rows from tracker")

    # Update tracker with discovered feeds
    updates_count = 0
    status_changes = 0
    updated_prospects = []

    print("\n🔄 Updating tracker with discovered feeds...\n")
    print("=" * 80)

    for row in rows:
        domain = row.get('Domain', '').strip()
        current_rss = row.get('RSS Feed', '').strip()
        current_status = row.get('Status', '').strip()
        current_data_source = row.get('Data Source', '').strip()

        if domain in discovered_feeds:
            new_rss = discovered_feeds[domain]

            # Only update if the feed is different or missing
            if new_rss and (not current_rss or current_rss == '-' or current_rss != new_rss):
                old_rss = current_rss
                old_status = current_status

                # Update RSS feed
                row['RSS Feed'] = new_rss

                # Update data source
                method = discovery_methods[domain]
                if method == 'autodiscovery':
                    row['Data Source'] = 'Discovered-autodiscovery'
                elif method == 'pattern':
                    row['Data Source'] = 'Discovered-pattern'
                elif method == 'sitemap':
                    row['Data Source'] = 'Discovered-sitemap'
                else:
                    row['Data Source'] = f'Discovered-{method}'

                # Update status based on current status
                if current_status in ['No feed generated', '']:
                    row['Status'] = 'To Do'
                    row['Comments'] = 'Newly discovered RSS feed'
                    status_changes += 1

                updates_count += 1
                updated_prospects.append({
                    'name': row['Prospect Name'],
                    'domain': domain,
                    'old_status': old_status if old_status else '[blank]',
                    'new_status': row['Status'],
                    'old_rss': old_rss if old_rss and old_rss != '-' else '[none]',
                    'new_rss': new_rss
                })

    # Show updates
    if updated_prospects:
        print(f"Updated {len(updated_prospects)} prospects:\n")
        for i, p in enumerate(updated_prospects[:20], 1):
            print(f"✅ {p['name'][:45]:45} | {p['domain'][:25]:25}")
            if p['old_status'] != p['new_status']:
                print(f"   Status: '{p['old_status']}' → '{p['new_status']}'")
            print(f"   RSS: {p['new_rss'][:65]}...")
            print()

        if len(updated_prospects) > 20:
            print(f"... and {len(updated_prospects) - 20} more\n")

    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   RSS feeds updated: {updates_count}")
    print(f"   Status changes to 'To Do': {status_changes}")

    # Write back to tracker
    print(f"\n💾 Writing updates to {tracker_file}...")
    with open(tracker_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Tracker updated successfully!")

    return updates_count, status_changes

if __name__ == '__main__':
    print("🔄 Updating Progress Tracker with Discovered RSS Feeds")
    print("=" * 80)
    updates, status_changes = update_tracker()
    print(f"\n✨ Done! {updates} RSS feeds added, {status_changes} statuses changed to 'To Do'")
