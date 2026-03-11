#!/usr/bin/env python3
"""
MASTER SYNC SCRIPT
Establishes the Progress Tracker as the single source of truth
by properly syncing all data sources in the correct priority order.

Data Source Priority:
1. current_feeds.txt - Hosted feeds (highest priority - ready for outreach)
2. tracking.csv - Scraper results
3. rss_discovery_results_enhanced.csv - Discovered original feeds
4. prospects.csv - Base prospect data

Status Definitions:
- "To Do" - Have hosted feed, ready to send
- "Sending" - Actively being sent
- "No feed generated" - No RSS feed found or scraping failed
- "Error adding feed to EBX" - Feed exists but error in platform
- Blank - Not yet processed
"""

import csv
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from config import Config
from collections import defaultdict

def load_hosted_feeds():
    """Load successfully generated hosted feeds from current_feeds.txt"""
    hosted = {}

    with open(Config.CURRENT_FEEDS_TXT, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Skip header lines
    for line in lines[3:]:
        parts = line.strip().split('\t')
        if len(parts) >= 4:
            name = parts[0].strip()
            feed = parts[1].strip()
            data_source = parts[2].strip()
            status = parts[3].strip()

            hosted[name] = {
                'feed': feed if feed != '-' else None,
                'data_source': data_source,
                'scrape_status': status
            }

    return hosted

def load_tracking_data():
    """Load scraper tracking data"""
    tracking = {}

    with open(Config.TRACKING_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['company_name'].strip()
            tracking[name] = {
                'domain': row['domain'],
                'rss_url': row.get('rss_url', ''),
                'status': row['status'],
                'articles_found': row.get('articles_found', '0'),
                'error': row.get('error_message', ''),
                'data_source': row.get('data_source', '')
            }

    return tracking

def load_discovery_results():
    """Load RSS discovery results"""
    discovered = {}

    with open(Config.DISCOVERY_RESULTS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row['domain'].strip()
            discovered[domain] = {
                'feed': row['feed_url'].strip(),
                'method': row['discovery_method'].strip()
            }

    return discovered

def establish_truth():
    """Establish the tracker as the single source of truth"""

    print("=" * 80)
    print("ESTABLISHING TRACKER AS SINGLE SOURCE OF TRUTH")
    print("=" * 80)

    # Load all data sources
    print("\n📋 Loading data sources...")
    hosted_feeds = load_hosted_feeds()
    tracking_data = load_tracking_data()
    discovered_feeds = load_discovery_results()

    print(f"   ✅ Hosted feeds: {len(hosted_feeds)}")
    print(f"   ✅ Tracking data: {len(tracking_data)}")
    print(f"   ✅ Discovery results: {len(discovered_feeds)}")

    # Load tracker
    print(f"\n📋 Loading tracker...")
    tracker_file = Config.OUTREACH_TRACKER_CSV

    rows = []
    with open(tracker_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"   ✅ Loaded {len(rows)} tracker rows")

    # Sync logic
    print(f"\n🔄 Syncing data to tracker (priority order)...\n")

    stats = {
        'hosted_feed': 0,
        'original_feed': 0,
        'no_feed': 0,
        'status_to_todo': 0,
        'status_to_no_feed': 0,
        'kept_existing': 0
    }

    for row in rows:
        name = row['Prospect Name'].strip()
        domain = row['Domain'].strip()
        current_status = row['Status'].strip()
        current_feed = row['RSS Feed'].strip()

        # Skip if already in a final state (unless we have better data)
        final_states = ['Sending', 'Irrelevant prospect', 'Parent org',
                       'Insufficient/Old Content', 'Error adding feed to EBX',
                       'Content not retrieved (retry later)']

        if current_status in final_states:
            stats['kept_existing'] += 1
            continue

        # Priority 1: Hosted feeds (ready for outreach)
        if name in hosted_feeds and hosted_feeds[name]['feed']:
            row['RSS Feed'] = hosted_feeds[name]['feed']
            row['Data Source'] = hosted_feeds[name]['data_source']

            if current_status not in ['To Do', 'Sending']:
                row['Status'] = 'To Do'
                row['Comments'] = 'Hosted feed ready for outreach'
                stats['status_to_todo'] += 1

            stats['hosted_feed'] += 1

        # Priority 2: Discovered original feeds (need processing)
        elif domain in discovered_feeds and discovered_feeds[domain]['feed']:
            # Only set original feed if we don't have a hosted one
            if 'swelbyboy.github.io' not in current_feed:
                row['RSS Feed'] = discovered_feeds[domain]['feed']

                method = discovered_feeds[domain]['method']
                if method == 'autodiscovery':
                    row['Data Source'] = 'Discovered-autodiscovery'
                elif method == 'pattern':
                    row['Data Source'] = 'Discovered-pattern'
                elif method == 'sitemap':
                    row['Data Source'] = 'Discovered-sitemap'

            # Keep status as "To Do" even with original feed (pending processing)
            if current_status == '':
                row['Status'] = 'To Do'
                row['Comments'] = 'Original RSS feed found - needs scraping'
                stats['status_to_todo'] += 1

            stats['original_feed'] += 1

        # Priority 3: No feed found
        else:
            # Check if scraping was attempted and failed
            if name in hosted_feeds and not hosted_feeds[name]['feed']:
                row['RSS Feed'] = '-'
                if current_status in ['', 'To Do']:
                    row['Status'] = 'No feed generated'
                    row['Comments'] = 'Scraping failed or no feed available'
                    stats['status_to_no_feed'] += 1
                stats['no_feed'] += 1

            # Or if discovery found nothing
            elif domain in discovered_feeds and not discovered_feeds[domain]['feed']:
                row['RSS Feed'] = '-'
                if current_status == '':
                    row['Status'] = 'No feed generated'
                    row['Comments'] = 'RSS discovery found no feed'
                    stats['status_to_no_feed'] += 1
                stats['no_feed'] += 1

    print("=" * 80)
    print("\n📊 Sync Summary:")
    print(f"   Hosted feeds (ready):        {stats['hosted_feed']:>5}")
    print(f"   Original feeds (need scrape): {stats['original_feed']:>5}")
    print(f"   No feed available:            {stats['no_feed']:>5}")
    print(f"   Kept existing status:         {stats['kept_existing']:>5}")
    print(f"\n   Status → 'To Do':             {stats['status_to_todo']:>5}")
    print(f"   Status → 'No feed generated': {stats['status_to_no_feed']:>5}")

    # Write back
    print(f"\n💾 Writing to {tracker_file}...")
    with open(tracker_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("✅ Tracker is now the single source of truth!")
    print("\n" + "=" * 80)

    return stats

if __name__ == '__main__':
    establish_truth()
