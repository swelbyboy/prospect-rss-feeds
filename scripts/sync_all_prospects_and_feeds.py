#!/usr/bin/env python3
"""
Comprehensive sync script to:
1. Add missing prospects from prospects.csv to tracker
2. Match XML files to prospects and update RSS Feed column
3. Update status for prospects with hosted feeds
"""

import csv
import os
from collections import defaultdict

def load_xml_files():
    """Load all XML files and create mapping"""
    xml_files = {}
    xml_by_name = defaultdict(list)
    
    # Scan feeds/ directory
    if os.path.exists('feeds'):
        for f in os.listdir('feeds'):
            if f.endswith('.xml'):
                xml_url = f'https://swelbyboy.github.io/prospect-rss-feeds/{f}'
                xml_files[f.lower()] = xml_url
                # Create slug for matching
                slug = f.lower().replace('.xml', '').replace('-', ' ').replace('_', ' ')
                xml_by_name[slug].append(xml_url)
    
    # Scan root directory
    for f in os.listdir('.'):
        if f.endswith('.xml'):
            xml_url = f'https://swelbyboy.github.io/prospect-rss-feeds/{f}'
            xml_files[f.lower()] = xml_url
            slug = f.lower().replace('.xml', '').replace('-', ' ').replace('_', ' ')
            xml_by_name[slug].append(xml_url)
    
    return xml_files, xml_by_name

def normalize_name(name):
    """Normalize prospect name for matching"""
    return name.lower().strip().replace(' ', '-').replace('.', '').replace(',', '').replace('&', 'and').replace("'", '').replace('"', '')

def match_xml_to_prospect(prospect_name, domain, xml_by_name):
    """Try to match XML file to prospect"""
    # Try exact match
    slug = normalize_name(prospect_name)
    if slug in xml_by_name:
        return xml_by_name[slug][0]
    
    # Try partial match
    prospect_words = prospect_name.lower().split()
    for xml_slug, urls in xml_by_name.items():
        xml_words = xml_slug.split()
        # Check if most words match
        matches = sum(1 for word in prospect_words if word in xml_slug)
        if matches >= min(2, len(prospect_words)):
            return urls[0]
    
    return None

def main():
    print("🔄 Comprehensive Sync: Prospects + Feeds\n")
    
    # Load all data
    print("📋 Loading data...")
    
    # Load prospects
    with open('prospects.csv', 'r', encoding='utf-8') as f:
        prospects = {row.get('domain', '').strip().lower(): row for row in csv.DictReader(f)}
    print(f"   ✅ Loaded {len(prospects):,} prospects")
    
    # Load tracker
    tracker_file = 'outreach_progress_tracker.csv'
    with open(tracker_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        tracker_rows = list(reader)
        tracker = {row.get('Domain', '').strip().lower(): row for row in tracker_rows}
    print(f"   ✅ Loaded {len(tracker):,} tracker entries")
    
    # Load XML files
    xml_files, xml_by_name = load_xml_files()
    print(f"   ✅ Found {len(xml_files):,} XML feed files")
    
    # Statistics
    stats = {
        'added': 0,
        'updated_rss': 0,
        'updated_status': 0,
        'matched_xml': 0
    }
    
    # Step 1: Add missing prospects
    print(f"\n📝 Step 1: Adding missing prospects...")
    missing_count = 0
    for domain, prospect in prospects.items():
        if domain and domain not in tracker:
            missing_count += 1
            # Try to match XML file
            xml_url = match_xml_to_prospect(
                prospect.get('company_name', ''),
                domain,
                xml_by_name
            )
            
            # Determine status
            if xml_url:
                status = 'To Do'
                rss_feed = xml_url
                data_source = 'Hosted feed exists'
                stats['matched_xml'] += 1
            elif prospect.get('rss_feed', '').strip():
                status = 'To Do'
                rss_feed = prospect.get('rss_feed', '').strip()
                data_source = 'Original feed from prospects.csv'
            else:
                status = ''
                rss_feed = '-'
                data_source = 'N/A'
            
            # Create new row
            new_row = {
                'Prospect Name': prospect.get('company_name', ''),
                'RSS Feed': rss_feed,
                'Data Source': data_source,
                'Last Scrape Status': '-',
                'Last Scrape Timestamp': '-',
                'Country': prospect.get('country', ''),
                'Domain': domain,
                'Status': status,
                'Existing newsletter?': 'FALSE',
                'Person': '',
                'Date sent': '',
                'Replied': 'FALSE',
                'Comments': 'Added from prospects.csv'
            }
            
            tracker_rows.append(new_row)
            tracker[domain] = new_row
            stats['added'] += 1
    
    print(f"   ✅ Added {missing_count:,} missing prospects")
    print(f"      - {stats['matched_xml']:,} matched to existing XML files")
    
    # Step 2: Update existing tracker entries with XML files
    print(f"\n🔄 Step 2: Updating tracker with XML files...")
    for row in tracker_rows:
        domain = row.get('Domain', '').strip().lower()
        prospect_name = row.get('Prospect Name', '').strip()
        current_rss = row.get('RSS Feed', '').strip()
        current_status = row.get('Status', '').strip()
        
        # Skip if already has hosted feed
        if 'swelbyboy.github.io' in current_rss:
            continue
        
        # Try to match XML file
        xml_url = match_xml_to_prospect(prospect_name, domain, xml_by_name)
        
        if xml_url:
            # Update RSS Feed
            if current_rss != xml_url:
                row['RSS Feed'] = xml_url
                row['Data Source'] = 'Hosted feed (matched from XML files)'
                stats['updated_rss'] += 1
            
            # Update status if needed
            if current_status in ['', 'No feed generated']:
                row['Status'] = 'To Do'
                row['Comments'] = 'Hosted feed found and matched'
                stats['updated_status'] += 1
    
    print(f"   ✅ Updated {stats['updated_rss']:,} RSS Feed URLs")
    print(f"   ✅ Updated {stats['updated_status']:,} statuses to 'To Do'")
    
    # Step 3: Update status for "To Do" entries that have hosted feeds
    print(f"\n✅ Step 3: Verifying 'To Do' entries have hosted feeds...")
    verified_count = 0
    for row in tracker_rows:
        if row.get('Status', '').strip() == 'To Do':
            rss_feed = row.get('RSS Feed', '').strip()
            if 'swelbyboy.github.io' in rss_feed:
                verified_count += 1
            else:
                # Try to find XML file
                xml_url = match_xml_to_prospect(
                    row.get('Prospect Name', ''),
                    row.get('Domain', ''),
                    xml_by_name
                )
                if xml_url:
                    row['RSS Feed'] = xml_url
                    row['Data Source'] = 'Hosted feed (matched from XML files)'
                    verified_count += 1
    
    print(f"   ✅ Verified {verified_count:,} 'To Do' entries have hosted feeds")
    
    # Write updated tracker
    print(f"\n💾 Writing updated tracker...")
    with open(tracker_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tracker_rows)
    
    # Final summary
    print(f"\n📊 Final Summary:")
    print(f"   Total prospects in tracker: {len(tracker_rows):,}")
    print(f"   Prospects with hosted feeds: {sum(1 for r in tracker_rows if 'swelbyboy.github.io' in r.get('RSS Feed', '')):,}")
    print(f"   Prospects with 'To Do' status: {sum(1 for r in tracker_rows if r.get('Status', '').strip() == 'To Do'):,}")
    print(f"   Prospects needing RSS discovery: {sum(1 for r in tracker_rows if not r.get('Status', '').strip() and r.get('RSS Feed', '').strip() == '-'):,}")
    print(f"\n✅ Tracker sync complete!")

if __name__ == '__main__':
    main()

