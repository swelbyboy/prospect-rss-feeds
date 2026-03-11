#!/usr/bin/env python3
"""
Update the Newsletter outreach tracker with latest scraping data
while preserving manual outreach tracking columns.
"""

import csv
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from config import Config
from datetime import datetime
from collections import defaultdict

def load_prospects():
    """Load prospects.csv for basic info"""
    prospects = {}
    with open(Config.PROSPECTS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row['domain']
            prospects[domain] = {
                'id': row['id'],
                'company_name': row['company_name'],
                'domain': domain,
                'rss_feed': row.get('rss_feed', ''),
                'country': row.get('country', '')
            }
    return prospects

def load_tracking():
    """Load tracking.csv for latest scrape status"""
    tracking = {}
    with open(Config.TRACKING_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = row['domain']
            tracking[domain] = {
                'last_scrape_date': row.get('last_scrape_date', ''),
                'status': row.get('status', ''),
                'articles_found': row.get('articles_found', '0'),
                'data_source': row.get('data_source', ''),
                'rss_url': row.get('rss_url', ''),
                'error_message': row.get('error_message', '')
            }
    return tracking

def load_discovery():
    """Load rss_discovery_results_enhanced.csv for newly discovered feeds"""
    discovery = {}
    try:
        with open(Config.DISCOVERY_RESULTS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                domain = row['domain']
                discovery[domain] = {
                    'feed_url': row.get('feed_url', ''),
                    'discovery_method': row.get('discovery_method', '')
                }
    except FileNotFoundError:
        print("⚠️  rss_discovery_results_enhanced.csv not found")
    return discovery

def load_existing_tracker():
    """Load existing outreach tracker to preserve manual columns"""
    tracker = {}
    input_file = os.path.join(Config.PROSPECTS_DIR, 'prospect_tracker.csv')
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                domain = row.get('Domain', '')
                if domain:
                    tracker[domain] = {
                        'Status': row.get('Status', ''),
                        'Existing newsletter?': row.get('Existing newsletter?', ''),
                        'Person': row.get('Person', ''),
                        'Date sent': row.get('Date sent', ''),
                        'Replied': row.get('Replied', ''),
                        'Comments': row.get('Comments', '')
                    }
        print(f"✅ Loaded {len(tracker)} existing tracked prospects")
    except FileNotFoundError:
        print("⚠️  Existing tracker not found, creating new one")
    
    return tracker

def update_outreach_tracker():
    """Update outreach tracker with latest data"""
    print("🔄 Updating outreach tracker...")
    
    # Load all data sources
    prospects = load_prospects()
    tracking = load_tracking()
    discovery = load_discovery()
    existing_tracker = load_existing_tracker()
    
    output_file = os.path.join(Config.PROSPECTS_DIR, 'prospect_tracker.csv')
    backup_file = os.path.join(Config.PROSPECTS_DIR, f'prospect_tracker-BACKUP-{datetime.now().strftime("%Y%m%d-%H%M%S")}.csv')
    
    # Backup existing file
    try:
        import shutil
        shutil.copy(output_file, backup_file)
        print(f"💾 Backup created: {backup_file}")
    except FileNotFoundError:
        pass
    
    # Write updated tracker
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        fieldnames = [
            'Prospect Name',
            'RSS Feed',
            'Data Source',
            'Last Scrape Status',
            'Last Scrape Timestamp',
            'Country',
            'Domain',
            'Status',
            'Existing newsletter?',
            'Person',
            'Date sent',
            'Replied',
            'Comments'
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        stats = {
            'total': 0,
            'updated': 0,
            'new': 0,
            'with_feed': 0,
            'newly_discovered': 0,
            'set_to_do': 0
        }
        
        # Process all prospects
        for domain, prospect in sorted(prospects.items(), key=lambda x: int(x[1]['id'])):
            stats['total'] += 1
            
            # Get tracking info
            track_info = tracking.get(domain, {})
            
            # Get discovery info
            disc_info = discovery.get(domain, {})
            
            # Determine RSS feed (prefer discovered > existing > tracking)
            rss_feed = disc_info.get('feed_url') or prospect['rss_feed'] or track_info.get('rss_url', '')
            
            # Determine data source
            if disc_info.get('discovery_method'):
                data_source = f"Discovered-{disc_info['discovery_method']}"
                stats['newly_discovered'] += 1
            else:
                data_source = track_info.get('data_source', 'N/A')
            
            # Determine scrape status
            if track_info.get('status') == 'success':
                scrape_status = 'success'
            elif track_info.get('status') == 'failed':
                scrape_status = 'failed'
            else:
                scrape_status = '-' if not rss_feed else 'N/A'
            
            if rss_feed:
                stats['with_feed'] += 1
            
            # Get existing manual tracking data
            manual_data = existing_tracker.get(domain, {})
            
            if domain in existing_tracker:
                stats['updated'] += 1
            else:
                stats['new'] += 1
            
            # Set status to 'To Do' if we have a feed and no existing status
            existing_status = manual_data.get('Status', '').strip()
            if rss_feed and rss_feed != '-' and not existing_status:
                status = 'To Do'
                stats['set_to_do'] += 1
            else:
                status = existing_status
            
            row = {
                'Prospect Name': prospect['company_name'],
                'RSS Feed': rss_feed or '-',
                'Data Source': data_source,
                'Last Scrape Status': scrape_status,
                'Last Scrape Timestamp': track_info.get('last_scrape_date', ''),
                'Country': prospect['country'],
                'Domain': domain,
                'Status': status,
                'Existing newsletter?': manual_data.get('Existing newsletter?', ''),
                'Person': manual_data.get('Person', ''),
                'Date sent': manual_data.get('Date sent', ''),
                'Replied': manual_data.get('Replied', ''),
                'Comments': manual_data.get('Comments', '')
            }
            
            writer.writerow(row)
    
    # Print summary
    print("\n" + "="*80)
    print("✅ Outreach Tracker Updated!")
    print("="*80)
    print(f"📊 Total Prospects: {stats['total']:,}")
    print(f"🔄 Updated Existing: {stats['updated']:,}")
    print(f"🆕 New Entries: {stats['new']:,}")
    print(f"✅ With RSS Feed: {stats['with_feed']:,} ({stats['with_feed']/stats['total']*100:.1f}%)")
    print(f"🔍 Newly Discovered: {stats['newly_discovered']:,}")
    print(f"📋 Set to 'To Do': {stats['set_to_do']:,}")
    print(f"⏰ Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Output: {output_file}")
    print("="*80)

if __name__ == '__main__':
    update_outreach_tracker()

