#!/usr/bin/env python3
"""
Sync the progress tracker with the latest RSS feed discoveries from prospects.csv
"""

import csv
from datetime import datetime

def sync_tracker():
    # Read prospects.csv to get latest RSS feed data
    prospects_data = {}
    print("📋 Loading prospects.csv...")
    with open('prospects.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get('domain', '').strip()
            if domain:
                prospects_data[domain] = {
                    'name': row.get('name', ''),
                    'rss_feed': row.get('rss_feed', ''),
                    'country': row.get('country', ''),
                }

    print(f"✅ Loaded {len(prospects_data)} prospects from prospects.csv")

    # Read the tracker
    tracker_file = 'Newsletter outreach #2 - Progress tracker - UPDATED.csv'
    print(f"\n📋 Loading {tracker_file}...")

    rows = []
    with open(tracker_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"✅ Loaded {len(rows)} rows from tracker")

    # Update tracker with new RSS feed data
    updates_count = 0
    status_changes = 0

    print("\n🔄 Syncing RSS feeds and updating statuses...\n")
    print("=" * 80)

    for row in rows:
        domain = row.get('Domain', '').strip()
        current_rss = row.get('RSS Feed', '').strip()
        current_status = row.get('Status', '').strip()

        if domain and domain in prospects_data:
            prospect = prospects_data[domain]
            new_rss = prospect['rss_feed'].strip()

            # Update RSS feed if it's different and not empty
            if new_rss and new_rss != '-' and new_rss != current_rss:
                row['RSS Feed'] = new_rss
                updates_count += 1

                # If status was "No feed generated" and we now have a feed, change to "To Do"
                if current_status == 'No feed generated':
                    row['Status'] = 'To Do'
                    row['Comments'] = 'Newly discovered RSS feed'
                    status_changes += 1
                    print(f"✅ {prospect['name'][:50]:50} | {domain[:30]:30}")
                    print(f"   Status: 'No feed generated' → 'To Do'")
                    print(f"   RSS: {new_rss[:70]}...")
                    print()

            # Update country if missing
            if prospect['country'] and not row.get('Country', '').strip():
                row['Country'] = prospect['country']

    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   RSS feeds updated: {updates_count}")
    print(f"   Status changes (No feed → To Do): {status_changes}")

    # Write back to tracker
    print(f"\n💾 Writing updates to {tracker_file}...")
    with open(tracker_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Tracker updated successfully!")

    return updates_count, status_changes

if __name__ == '__main__':
    print("🔄 Syncing Progress Tracker with Prospects Data")
    print("=" * 80)
    updates, status_changes = sync_tracker()
    print(f"\n✨ Done! {updates} RSS feeds updated, {status_changes} statuses changed")
