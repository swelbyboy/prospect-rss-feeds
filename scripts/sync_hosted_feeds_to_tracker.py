#!/usr/bin/env python3
"""
Sync the tracker with hosted feed URLs from current_feeds.txt
This ensures the RSS Feed column contains the correct hosted feed URLs
"""

import csv
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from config import Config

def parse_current_feeds():
    """Parse current_feeds.txt to extract hosted feed URLs"""
    feeds = {}

    with open(Config.CURRENT_FEEDS_TXT, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Skip header lines (first 3 lines)
    for line in lines[3:]:
        parts = line.strip().split('\t')
        if len(parts) >= 4:
            prospect_name = parts[0].strip()
            rss_feed = parts[1].strip()
            data_source = parts[2].strip()
            last_status = parts[3].strip()

            feeds[prospect_name] = {
                'rss_feed': rss_feed if rss_feed != '-' else '',
                'data_source': data_source,
                'last_status': last_status
            }

    return feeds

def sync_tracker():
    # Parse current_feeds.txt
    print("📋 Loading current_feeds.txt...")
    hosted_feeds = parse_current_feeds()

    with_feed = sum(1 for f in hosted_feeds.values() if f['rss_feed'])
    without_feed = len(hosted_feeds) - with_feed

    print(f"✅ Loaded {len(hosted_feeds)} prospects from current_feeds")
    print(f"   With hosted feed: {with_feed}")
    print(f"   Failed/No feed: {without_feed}")

    # Read tracker
    tracker_file = os.path.join(Config.PROSPECTS_DIR, 'Newsletter outreach #2 - Progress tracker - UPDATED.csv')
    print(f"\n📋 Loading {tracker_file}...")

    rows = []
    with open(tracker_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"✅ Loaded {len(rows)} tracker rows")

    # Sync
    feeds_updated = 0
    status_to_todo = 0
    status_to_no_feed = 0

    print("\n🔄 Syncing hosted feeds to tracker...\n")
    print("=" * 80)

    for row in rows:
        prospect_name = row['Prospect Name'].strip()

        if prospect_name not in hosted_feeds:
            continue

        hosted = hosted_feeds[prospect_name]
        current_status = row['Status'].strip()

        # Update RSS Feed with hosted feed URL
        if hosted['rss_feed']:
            row['RSS Feed'] = hosted['rss_feed']
            row['Data Source'] = hosted['data_source']
            feeds_updated += 1

            # Update status to "To Do" if it's not already set to a working status
            if current_status in ['', 'No feed generated']:
                row['Status'] = 'To Do'
                row['Comments'] = 'Hosted feed generated successfully'
                status_to_todo += 1
                print(f"✅ {prospect_name[:60]:60} | To Do")

        # If no hosted feed (failed or no feed found)
        else:
            # Clear any incorrect feed URL
            if row['RSS Feed'] and 'swelbyboy.github.io' not in row['RSS Feed']:
                row['RSS Feed'] = '-'

            # Update status if currently "To Do" but we have no hosted feed
            if current_status == 'To Do':
                row['Status'] = 'No feed generated'
                row['Comments'] = 'Feed generation failed or no source feed found'
                status_to_no_feed += 1
                print(f"❌ {prospect_name[:60]:60} | No feed generated")

    print()
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   Hosted feeds updated: {feeds_updated}")
    print(f"   Status changed to 'To Do': {status_to_todo}")
    print(f"   Status changed to 'No feed generated': {status_to_no_feed}")

    # Write back
    print(f"\n💾 Writing to {tracker_file}...")
    with open(tracker_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("✅ Tracker updated with hosted feed URLs!")

    return feeds_updated, status_to_todo, status_to_no_feed

if __name__ == '__main__':
    print("🔄 Syncing Hosted Feeds to Progress Tracker")
    print("=" * 80)
    feeds, todo, no_feed = sync_tracker()
    print(f"\n✨ Done! {feeds} hosted feeds synced")
