#!/usr/bin/env python3
"""
RSS Feed Discovery Script
Discovers RSS feeds for prospects without rss_feed URLs by trying common patterns.
"""

import csv
import requests
import time
from urllib.parse import urljoin
import feedparser

# Common RSS feed URL patterns
RSS_PATTERNS = [
    '/feed',
    '/rss',
    '/feed.xml',
    '/rss.xml',
    '/atom.xml',
    '/feeds/posts/default',
    '/blog/feed',
    '/blog/rss',
    '/index.rss',
    '/news/rss',
    '/articles/feed',
]

def discover_rss_feed(domain, timeout=5):
    """
    Try to discover RSS feed for a domain.
    
    Args:
        domain: Domain to check (e.g., 'example.com')
        timeout: Request timeout in seconds
        
    Returns:
        tuple: (success, feed_url, error_message)
    """
    # Try both http and https
    schemes = ['https', 'http']
    
    for scheme in schemes:
        base_url = f"{scheme}://{domain}"
        
        for pattern in RSS_PATTERNS:
            feed_url = urljoin(base_url, pattern)
            
            try:
                # Make HEAD request first to check if URL exists
                response = requests.head(feed_url, timeout=timeout, allow_redirects=True)
                
                # If HEAD succeeds or returns 405 (Method Not Allowed), try GET
                if response.status_code in [200, 405]:
                    # Parse the feed to verify it's valid
                    feed = feedparser.parse(feed_url)
                    
                    # Check if feed has entries
                    if feed.entries and len(feed.entries) > 0:
                        print(f"      ✅ Found: {pattern}")
                        return (True, feed_url, None)
                        
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.ConnectionError:
                continue
            except Exception as e:
                continue
    
    return (False, None, "No RSS feed found")


def main():
    print("🔍 RSS Feed Discovery")
    print("=" * 80)
    
    # Read prospects without RSS feeds
    prospects = []
    with open('prospects.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('rss_feed', '').strip():
                prospects.append(row)
    
    print(f"📋 Found {len(prospects)} prospects without RSS feeds\n")
    
    # Discovery results
    found = 0
    not_found = 0
    results = []
    
    for i, prospect in enumerate(prospects, 1):
        company_name = prospect['company_name']
        domain = prospect['domain']
        prospect_id = prospect['id']
        
        print(f"[{i}/{len(prospects)}] {company_name} ({domain})...")
        
        success, feed_url, error = discover_rss_feed(domain)
        
        if success:
            found += 1
            results.append({
                'id': prospect_id,
                'domain': domain,
                'feed_url': feed_url
            })
        else:
            not_found += 1
        
        # Rate limiting
        time.sleep(0.5)
        
        # Progress update every 50 prospects
        if i % 50 == 0:
            print(f"\n   Progress: {i}/{len(prospects)} | Found: {found} | Not found: {not_found}\n")
    
    print("\n" + "=" * 80)
    print("📊 DISCOVERY SUMMARY")
    print("=" * 80)
    print(f"Total prospects checked: {len(prospects)}")
    print(f"✅ RSS feeds found: {found}")
    print(f"❌ Not found: {not_found}")
    print(f"Success rate: {(found/len(prospects)*100):.1f}%")
    print("=" * 80)
    
    # Write results to CSV
    if results:
        with open('rss_discovery_results.csv', 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'domain', 'feed_url'])
            writer.writeheader()
            writer.writerows(results)
        
        print(f"\n✅ Results written to: rss_discovery_results.csv")
        print(f"\nNext step: Run update script to add these feeds to prospects.csv")

if __name__ == '__main__':
    main()
