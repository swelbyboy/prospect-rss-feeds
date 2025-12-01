#!/usr/bin/env python3
"""
Sync RSS feeds and data from prospects.csv to the progress tracker
This ensures the tracker is updated with all newly discovered feeds
"""

import csv
from datetime import datetime

def sync_prospects_to_tracker():
    # Read prospects.csv
    print("📋 Loading prospects.csv...")
    prospects_data = {}

    with open('prospects.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row.get('domain', '').strip()
            if domain:
                prospects_data[domain] = {
                    'name': row.get('name', ''),
                    'rss_feed': row.get('rss_feed', '').strip(),
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

    # Sync data
    feeds_added = 0
    status_updated_to_todo = 0
    status_updated_to_no_feed = 0

    updated_prospects = []

    print("\n🔄 Syncing prospects.csv data to tracker...\n")
    print("=" * 80)

    for row in rows:
        domain = row.get('Domain', '').strip()
        current_rss = row.get('RSS Feed', '').strip()
        current_status = row.get('Status', '').strip()

        if domain and domain in prospects_data:
            prospect = prospects_data[domain]
            new_rss = prospect['rss_feed']

            # Update RSS feed if different
            if new_rss and new_rss != '-' and new_rss != current_rss:
                old_rss = current_rss if current_rss and current_rss != '-' else '[none]'
                row['RSS Feed'] = new_rss
                feeds_added += 1

                # Update status based on current status
                old_status = current_status if current_status else '[blank]'

                # If status is blank or "No feed generated", change to "To Do"
                if current_status in ['', 'No feed generated']:
                    row['Status'] = 'To Do'
                    row['Comments'] = 'Newly discovered RSS feed'
                    row['Data Source'] = 'Discovered-autodiscovery'  # Will be refined if we have discovery method data
                    status_updated_to_todo += 1

                    updated_prospects.append({
                        'name': row['Prospect Name'],
                        'domain': domain,
                        'old_status': old_status,
                        'new_rss': new_rss
                    })

            # For prospects with blank status and NO feed in prospects.csv
            # These were checked but no feed was found
            elif current_status == '' and (not new_rss or new_rss == '-'):
                # Check if this prospect was in the recent discovery run
                # For now, we'll leave them as blank since we don't have confirmation they were checked
                pass

            # Update country if missing
            if prospect['country'] and not row.get('Country', '').strip():
                row['Country'] = prospect['country']

    # Show sample updates
    if updated_prospects:
        print(f"Updated {len(updated_prospects)} prospects with new feeds:\n")
        for i, p in enumerate(updated_prospects[:30], 1):
            print(f"✅ {i:3}. {p['name'][:45]:45} | {p['domain'][:25]:25}")
            print(f"      Status: '{p['old_status']}' → 'To Do'")
            print(f"      RSS: {p['new_rss'][:65]}...")
            print()

        if len(updated_prospects) > 30:
            print(f"... and {len(updated_prospects) - 30} more\n")

    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   RSS feeds added/updated: {feeds_added}")
    print(f"   Statuses changed to 'To Do': {status_updated_to_todo}")

    # Write back to tracker
    print(f"\n💾 Writing updates to {tracker_file}...")
    with open(tracker_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Tracker updated successfully!")

    return feeds_added, status_updated_to_todo

if __name__ == '__main__':
    print("🔄 Syncing Prospects.csv to Progress Tracker")
    print("=" * 80)
    feeds, status_changes = sync_prospects_to_tracker()
    print(f"\n✨ Done! {feeds} RSS feeds synced, {status_changes} statuses changed to 'To Do'")
