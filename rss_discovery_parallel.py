#!/usr/bin/env python3
"""
Parallel RSS Feed Discovery Script
Discovers RSS feeds using multiple strategies with concurrent processing.
"""

import csv
import requests
import time
from urllib.parse import urljoin
import feedparser
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Expanded RSS feed URL patterns
RSS_PATTERNS = [
    '/feed', '/feed/', '/rss', '/rss/', '/feed.xml', '/rss.xml', '/atom.xml',
    '/blog/feed', '/blog/feed/', '/blog/rss', '/blog/rss.xml', '/blog/atom.xml',
    '/news/feed', '/news/rss', '/news/feed.xml',
    '/articles/feed', '/articles/rss',
    '/feeds/posts/default', '/feeds/posts/default?alt=rss',
    '/index.rss', '/index.xml', '/main.rss', '/site.rss', '/feed.rss',
    '/.rss', '/rss.php', '/feed.php',
    '/category/news/feed', '/section/news/feed',
]

def check_autodiscovery(domain, timeout=2):
    """Check HTML <link> tags for RSS autodiscovery."""
    for scheme in ['https', 'http']:
        base_url = f"{scheme}://{domain}"
        try:
            response = requests.get(base_url, timeout=timeout,
                                   headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                link_tags = soup.find_all('link', {
                    'rel': lambda x: x and ('alternate' in x.lower()),
                    'type': lambda x: x and ('rss' in x.lower() or 'atom' in x.lower() or 'xml' in x.lower())
                })
                for link in link_tags:
                    href = link.get('href')
                    if href:
                        feed_url = urljoin(base_url, href)
                        feed = feedparser.parse(feed_url)
                        if feed.entries and len(feed.entries) > 0:
                            return (True, feed_url, None)
        except Exception:
            continue
    return (False, None, "No autodiscovery link found")

def check_sitemap(domain, timeout=1):
    """Check sitemap.xml for RSS feed references."""
    for scheme in ['https', 'http']:
        sitemap_urls = [
            f"{scheme}://{domain}/sitemap.xml",
            f"{scheme}://{domain}/sitemap_index.xml",
        ]
        for sitemap_url in sitemap_urls:
            try:
                response = requests.get(sitemap_url, timeout=timeout)
                if response.status_code == 200:
                    content = response.text
                    feed_matches = re.findall(r'<loc>(.*?/(?:feed|rss|atom).*?)</loc>', content)
                    for feed_url in feed_matches:
                        feed = feedparser.parse(feed_url)
                        if feed.entries and len(feed.entries) > 0:
                            return (True, feed_url, None)
            except Exception:
                continue
    return (False, None, "No feed found in sitemap")

def check_common_patterns(domain, timeout=1):
    """Try common RSS feed URL patterns."""
    for scheme in ['https', 'http']:
        base_url = f"{scheme}://{domain}"
        for pattern in RSS_PATTERNS:
            feed_url = urljoin(base_url, pattern)
            try:
                response = requests.head(feed_url, timeout=timeout, allow_redirects=True,
                                        headers={'User-Agent': 'Mozilla/5.0'})
                if response.status_code in [200, 405]:
                    feed = feedparser.parse(feed_url)
                    if feed.entries and len(feed.entries) > 0:
                        return (True, feed_url, None)
            except Exception:
                continue
    return (False, None, "No feed found with common patterns")

def discover_rss_feed(domain):
    """Comprehensive RSS feed discovery using multiple strategies."""
    # Strategy 1: HTML Autodiscovery (most reliable)
    success, feed_url, error = check_autodiscovery(domain)
    if success:
        return (True, feed_url, "autodiscovery", None)

    # Strategy 2: Common URL patterns (fast)
    success, feed_url, error = check_common_patterns(domain)
    if success:
        return (True, feed_url, "pattern", None)

    # Strategy 3: Sitemap.xml (less common but worth trying)
    success, feed_url, error = check_sitemap(domain)
    if success:
        return (True, feed_url, "sitemap", None)

    return (False, None, None, "No RSS feed found with any method")

def process_prospect(prospect, index, total, print_lock):
    """Process a single prospect (thread-safe)."""
    company_name = prospect['company_name']
    domain = prospect['domain']
    prospect_id = prospect['id']

    with print_lock:
        print(f"[{index}/{total}] {company_name} ({domain})")

    success, feed_url, method, error = discover_rss_feed(domain)

    result = {
        'prospect': prospect,
        'success': success,
        'feed_url': feed_url,
        'method': method,
        'error': error
    }

    with print_lock:
        if success:
            print(f"      ✅ Found via {method}")
        else:
            print(f"      ❌ {error}")

    return result

def main():
    print("🔍 Parallel RSS Feed Discovery")
    print("=" * 80)

    # Read prospects without RSS feeds
    prospects = []
    with open('prospects.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('rss_feed', '').strip():
                prospects.append(row)

    print(f"📋 Found {len(prospects)} prospects without RSS feeds")

    # Get remaining prospects (skip already processed)
    try:
        with open('rss_discovery_output.log', 'r') as f:
            log_content = f.read()
            # Find last processed prospect number
            matches = re.findall(r'\[(\d+)/\d+\]', log_content)
            if matches:
                last_processed = int(matches[-1])
                prospects = prospects[last_processed:]
                print(f"🔄 Resuming from prospect #{last_processed + 1}")
    except FileNotFoundError:
        pass

    if len(prospects) == 0:
        print("✅ All prospects processed!")
        return

    print(f"⚡ Processing {len(prospects)} prospects with 10 parallel workers\n")

    # Discovery results
    found = 0
    not_found = 0
    results = []
    methods = {'autodiscovery': 0, 'pattern': 0, 'sitemap': 0}
    print_lock = Lock()

    # Process prospects in parallel with ThreadPoolExecutor
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all tasks
        future_to_prospect = {
            executor.submit(process_prospect, prospect, i, len(prospects), print_lock): (prospect, i)
            for i, prospect in enumerate(prospects, 1)
        }

        # Process completed tasks
        for future in as_completed(future_to_prospect):
            prospect, index = future_to_prospect[future]
            try:
                result = future.result()

                if result['success']:
                    found += 1
                    methods[result['method']] += 1
                    results.append({
                        'id': result['prospect']['id'],
                        'company_name': result['prospect']['company_name'],
                        'domain': result['prospect']['domain'],
                        'feed_url': result['feed_url'],
                        'discovery_method': result['method']
                    })
                else:
                    not_found += 1

                # Progress update every 25 prospects
                if index % 25 == 0:
                    elapsed = time.time() - start_time
                    rate = index / elapsed if elapsed > 0 else 0
                    remaining = (len(prospects) - index) / rate if rate > 0 else 0
                    with print_lock:
                        print(f"\n   Progress: {index}/{len(prospects)} | Found: {found} ({found/index*100:.1f}%) | Rate: {rate:.1f}/sec | ETA: {remaining/60:.0f}m\n")

            except Exception as exc:
                with print_lock:
                    print(f"      ❌ Error: {exc}")
                not_found += 1

    elapsed_time = time.time() - start_time

    print("\n" + "=" * 80)
    print("📊 DISCOVERY SUMMARY")
    print("=" * 80)
    print(f"Total prospects checked: {len(prospects)}")
    print(f"✅ RSS feeds found: {found} ({found/len(prospects)*100:.1f}%)")
    print(f"❌ Not found: {not_found} ({not_found/len(prospects)*100:.1f}%)")
    print(f"⏱️  Time taken: {elapsed_time/60:.1f} minutes")
    print(f"⚡ Rate: {len(prospects)/elapsed_time:.1f} prospects/second")
    print(f"\nDiscovery methods:")
    print(f"  Autodiscovery: {methods['autodiscovery']}")
    print(f"  URL patterns: {methods['pattern']}")
    print(f"  Sitemap: {methods['sitemap']}")
    print("=" * 80)

    # Write results to CSV
    if results:
        # Load existing results if any
        existing_results = []
        try:
            with open('rss_discovery_results_enhanced.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                existing_results = list(reader)
        except FileNotFoundError:
            pass

        # Merge and write
        all_results = existing_results + results
        with open('rss_discovery_results_enhanced.csv', 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'company_name', 'domain', 'feed_url', 'discovery_method'])
            writer.writeheader()
            writer.writerows(all_results)

        print(f"\n✅ Results written to: rss_discovery_results_enhanced.csv")
        print(f"\n💡 Next: Run update script to add {len(all_results)} feeds to prospects.csv")
    else:
        print(f"\n⚠️  No new feeds discovered")

if __name__ == '__main__':
    main()
