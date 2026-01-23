#!/usr/bin/env python3
"""
Add new prospects from prospects.csv to outreach_progress_tracker.csv

This script must be run BEFORE rss_discovery.py when adding new prospects.
The discovery script reads from the tracker, not from prospects.csv directly.
"""

import csv
import sys

PROSPECTS_FILE = 'prospects.csv'
TRACKER_FILE = 'outreach_progress_tracker.csv'

def main():
    print("📥 Adding new prospects to outreach_progress_tracker.csv")
    print("=" * 80)

    # Load existing tracker
    tracker_rows = []
    existing_domains = set()

    with open(TRACKER_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            tracker_rows.append(row)
            domain = row.get('Domain', '').strip().lower()
            if domain:
                existing_domains.add(domain)

    print(f"📋 Loaded {len(tracker_rows)} existing tracker rows")
    print(f"   Unique domains in tracker: {len(existing_domains)}")

    # Load prospects
    prospects = []
    with open(PROSPECTS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        prospects = list(reader)

    print(f"📋 Loaded {len(prospects)} prospects from prospects.csv")

    # Find new prospects not in tracker
    new_rows = []
    for prospect in prospects:
        domain = prospect.get('domain', '').strip().lower()
        if not domain:
            continue

        if domain not in existing_domains:
            # Add new prospect to tracker
            new_row = {
                'Prospect Name': prospect.get('company_name', ''),
                'RSS Feed': prospect.get('rss_feed', '') or '-',
                'Data Source': '',
                'Last Scrape Status': '',
                'Last Scrape Timestamp': '',
                'Country': prospect.get('country', ''),
                'Domain': prospect.get('domain', ''),
                'Status': '',  # Blank status = needs RSS discovery
                'Existing newsletter?': 'FALSE',
                'Person': '',
                'Date sent': '',
                'Replied': 'FALSE',
                'Comments': ''
            }
            new_rows.append(new_row)
            existing_domains.add(domain)

    print(f"\n✨ Found {len(new_rows)} new prospects to add")

    if not new_rows:
        print("✅ No new prospects to add - tracker is up to date!")
        return 0

    # Combine and save
    all_rows = tracker_rows + new_rows

    with open(TRACKER_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\n💾 Saved {len(all_rows)} total rows to {TRACKER_FILE}")
    print(f"   (was {len(tracker_rows)}, added {len(new_rows)})")
    print("=" * 80)
    print("\n✅ Done! New prospects added with blank Status (ready for RSS discovery)")
    print("\n💡 Next step: Run RSS discovery to find feeds:")
    print("   python3 rss_discovery.py")

    return len(new_rows)

if __name__ == '__main__':
    added = main()
    sys.exit(0 if added >= 0 else 1)
