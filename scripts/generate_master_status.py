#!/usr/bin/env python3
"""
Generate a master status CSV that consolidates all prospect information:
- Basic prospect info from prospects.csv
- Scraping status from tracking.csv
- Discovery results from rss_discovery_results_enhanced.csv
"""

import csv
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from config import Config
from datetime import datetime
from collections import defaultdict

def load_prospects():
    """Load basic prospect info"""
    prospects = {}
    with open(Config.PROSPECTS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            prospects[row['id']] = {
                'id': row['id'],
                'company_name': row['company_name'],
                'domain': row['domain'],
                'rss_feed': row.get('rss_feed', ''),
                'country': row.get('country', ''),
                'email': row.get('email', ''),
                'contact_name': row.get('contact_name', ''),
                'notes': row.get('notes', '')
            }
    return prospects

def load_tracking():
    """Load scraping status"""
    tracking = {}
    with open(Config.TRACKING_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tracking[row['prospect_id']] = {
                'last_scrape_date': row.get('last_scrape_date', ''),
                'scrape_status': row.get('status', ''),
                'articles_found': row.get('articles_found', '0'),
                'data_source': row.get('data_source', ''),
                'error_message': row.get('error_message', '')
            }
    return tracking

def load_discovery():
    """Load RSS discovery results"""
    discovery = {}
    try:
        with open(Config.DISCOVERY_RESULTS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                domain = row['domain']
                discovery[domain] = {
                    'discovered_feed': row.get('feed_url', ''),
                    'discovery_method': row.get('discovery_method', '')
                }
    except FileNotFoundError:
        print("⚠️  rss_discovery_results_enhanced.csv not found, skipping discovery data")
    return discovery

def generate_master_status():
    """Generate consolidated master status file"""
    print("📊 Generating master status file...")
    
    # Load all data
    prospects = load_prospects()
    tracking = load_tracking()
    discovery = load_discovery()
    
    # Create domain-to-id mapping for discovery lookups
    domain_to_id = {p['domain']: pid for pid, p in prospects.items()}
    
    # Write consolidated file
    with open(Config.MASTER_STATUS_CSV, 'w', encoding='utf-8', newline='') as f:
        fieldnames = [
            'id',
            'company_name',
            'domain',
            'country',
            'has_rss_feed',
            'current_rss_feed',
            'discovered_feed',
            'discovery_method',
            'data_source',
            'last_scrape_date',
            'scrape_status',
            'articles_found',
            'error_message',
            'email',
            'contact_name',
            'notes'
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        stats = {
            'total': 0,
            'with_feed': 0,
            'without_feed': 0,
            'newly_discovered': 0,
            'scrape_success': 0,
            'scrape_failed': 0
        }
        
        for prospect_id, prospect in sorted(prospects.items(), key=lambda x: int(x[0])):
            stats['total'] += 1
            
            # Get tracking info
            track_info = tracking.get(prospect_id, {})
            
            # Get discovery info
            disc_info = discovery.get(prospect['domain'], {})
            
            # Determine current RSS feed
            current_feed = prospect['rss_feed'] or disc_info.get('discovered_feed', '')
            has_feed = 'Yes' if current_feed else 'No'
            
            if current_feed:
                stats['with_feed'] += 1
            else:
                stats['without_feed'] += 1
            
            if disc_info.get('discovered_feed'):
                stats['newly_discovered'] += 1
            
            if track_info.get('scrape_status') == 'success':
                stats['scrape_success'] += 1
            elif track_info.get('scrape_status') == 'failed':
                stats['scrape_failed'] += 1
            
            row = {
                'id': prospect['id'],
                'company_name': prospect['company_name'],
                'domain': prospect['domain'],
                'country': prospect['country'],
                'has_rss_feed': has_feed,
                'current_rss_feed': current_feed,
                'discovered_feed': disc_info.get('discovered_feed', ''),
                'discovery_method': disc_info.get('discovery_method', ''),
                'data_source': track_info.get('data_source', ''),
                'last_scrape_date': track_info.get('last_scrape_date', ''),
                'scrape_status': track_info.get('scrape_status', ''),
                'articles_found': track_info.get('articles_found', ''),
                'error_message': track_info.get('error_message', ''),
                'email': prospect['email'],
                'contact_name': prospect['contact_name'],
                'notes': prospect['notes']
            }
            
            writer.writerow(row)
    
    # Print statistics
    print("\n" + "="*80)
    print("✅ Master Status Generated: master_status.csv")
    print("="*80)
    print(f"📊 Total Prospects: {stats['total']:,}")
    print(f"✅ With RSS Feed: {stats['with_feed']:,} ({stats['with_feed']/stats['total']*100:.1f}%)")
    print(f"❌ Without RSS Feed: {stats['without_feed']:,} ({stats['without_feed']/stats['total']*100:.1f}%)")
    print(f"🆕 Newly Discovered: {stats['newly_discovered']:,}")
    print(f"✅ Scrape Success: {stats['scrape_success']:,}")
    print(f"❌ Scrape Failed: {stats['scrape_failed']:,}")
    print(f"⏰ Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

if __name__ == '__main__':
    generate_master_status()

