#!/usr/bin/env python3
"""
Parallel RSS Feed Discovery Script
Discovers RSS feeds using multiple strategies with concurrent processing.
Features: parallel processing, incremental saving, resume capability.
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
import signal
import sys
import os
import subprocess

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

OUTPUT_FILE = 'rss_discovery_results_enhanced.csv'

# Global for signal handling
executor = None
should_exit = False

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    global should_exit
    print('\n\n⚠️  Interrupt received. Finishing current tasks and saving...')
    should_exit = True
    if executor:
        executor.shutdown(wait=False)

signal.signal(signal.SIGINT, signal_handler)

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

def save_result(result, file_lock):
    """Save a single result to CSV immediately (thread-safe)."""
    with file_lock:
        file_exists = os.path.exists(OUTPUT_FILE)
        with open(OUTPUT_FILE, 'a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'company_name', 'domain', 'feed_url', 'discovery_method'])
            if not file_exists:
                writer.writeheader()
            writer.writerow(result)

def load_processed_domains():
    """Load already-processed domains from the CSV file."""
    processed = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    processed.add(row['domain'])
        except Exception as e:
            print(f"⚠️  Could not load existing results: {e}")
    return processed

def commit_progress():
    """Commit progress to git if running in CI environment."""
    if not os.environ.get('GITHUB_CI'):
        return  # Only commit in GitHub Actions
    
    try:
        # Check if there are changes
        result = subprocess.run(['git', 'diff', '--quiet', OUTPUT_FILE], 
                              capture_output=True)
        if result.returncode == 0:
            return  # No changes
        
        # Add and commit
        subprocess.run(['git', 'add', OUTPUT_FILE], check=True)
        count = subprocess.run(['wc', '-l', OUTPUT_FILE], 
                             capture_output=True, text=True).stdout.strip().split()[0]
        subprocess.run(['git', 'commit', '-m', 
                       f'Auto-save RSS discovery progress: {count} entries'],
                      check=True)
        
        # Pull and push
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], check=True)
        subprocess.run(['git', 'push'], check=True)
        print(f"      💾 Progress auto-committed ({count} entries)")
    except Exception as e:
        print(f"      ⚠️  Could not commit progress: {e}")

def process_prospect(prospect, index, total, print_lock, file_lock, stats):
    """Process a single prospect (thread-safe)."""
    global should_exit
    if should_exit:
        return None

    company_name = prospect['company_name']
    domain = prospect['domain']
    prospect_id = prospect['id']

    with print_lock:
        print(f"[{index}/{total}] {company_name} ({domain})")
        print(f"      🔍 Checking autodiscovery...")

    success, feed_url, method, error = discover_rss_feed(domain)

    # Always save the result (whether found or not) to avoid re-processing
    result = {
        'id': prospect_id,
        'company_name': company_name,
        'domain': domain,
        'feed_url': feed_url if success else '',
        'discovery_method': method if success else 'not_found'
    }
    # Save immediately
    save_result(result, file_lock)

    if success:
        with print_lock:
            print(f"      ✅ Found via {method}")
            stats['found'] += 1
            stats['methods'][method] += 1

        return result
    else:
        with print_lock:
            print(f"      🔍 Trying common patterns...")
            print(f"      🔍 Checking sitemap...")
            print(f"      ❌ {error}")
            stats['not_found'] += 1

        return None

def main():
    global executor

    print("🔍 Parallel RSS Feed Discovery (with auto-save)")
    print("=" * 80)

    # Read prospects from prospects.csv where rss_feed is empty
    # This is the master list of all prospects
    
    prospects_to_search = []
    try:
        with open('prospects.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rss_feed = row.get('rss_feed', '').strip()
                
                # Only discover feeds for prospects without an RSS feed
                if not rss_feed:
                    prospects_to_search.append({
                        'id': row.get('id', ''),
                        'company_name': row.get('company_name', ''),
                        'domain': row.get('domain', '')
                    })
        
        print(f"📋 Loaded {len(prospects_to_search)} prospects without RSS feeds from prospects.csv")
        print(f"   (These prospects need RSS feed discovery)\n")
    
    except FileNotFoundError:
        print("❌ prospects.csv not found")
        print("   Please ensure the file exists in the current directory")
        sys.exit(1)
    
    prospects = prospects_to_search

    # Load already-processed domains
    processed_domains = load_processed_domains()
    if processed_domains:
        original_count = len(prospects)
        prospects = [p for p in prospects if p['domain'] not in processed_domains]
        skipped = original_count - len(prospects)
        print(f"✅ Skipping {skipped} already-processed prospects")
        print(f"📊 Remaining prospects to process: {len(prospects)}")

    if len(prospects) == 0:
        print("✅ All prospects processed!")
        return

    print(f"⚡ Processing {len(prospects)} prospects with 10 parallel workers")
    print(f"💾 Results auto-save to: {OUTPUT_FILE}\n")

    # Stats (thread-safe with lock)
    stats = {
        'found': 0,
        'not_found': 0,
        'methods': {'autodiscovery': 0, 'pattern': 0, 'sitemap': 0}
    }
    print_lock = Lock()
    file_lock = Lock()

    # Process prospects in parallel
    start_time = time.time()
    completed_count = 0

    executor = ThreadPoolExecutor(max_workers=10)
    try:
        # Submit all tasks
        future_to_prospect = {
            executor.submit(process_prospect, prospect, i, len(prospects), print_lock, file_lock, stats): (prospect, i)
            for i, prospect in enumerate(prospects, 1)
        }

        # Process completed tasks
        for future in as_completed(future_to_prospect):
            if should_exit:
                break

            prospect, index = future_to_prospect[future]
            try:
                result = future.result()
                completed_count += 1

                # Progress update every 25 prospects
                if completed_count % 25 == 0:
                    elapsed = time.time() - start_time
                    rate = completed_count / elapsed if elapsed > 0 else 0
                    remaining = (len(prospects) - completed_count) / rate if rate > 0 else 0
                    with print_lock:
                        print(f"\n   Progress: {completed_count}/{len(prospects)} | Found: {stats['found']} ({stats['found']/completed_count*100:.1f}%) | Not found: {stats['not_found']}\n")
                
                # Auto-commit progress every 100 prospects (in CI only)
                if completed_count % 100 == 0:
                    commit_progress()

            except Exception as exc:
                with print_lock:
                    print(f"      ❌ Error: {exc}")
                stats['not_found'] += 1

    finally:
        executor.shutdown(wait=True)

    elapsed_time = time.time() - start_time

    print("\n" + "=" * 80)
    print("📊 DISCOVERY SUMMARY")
    print("=" * 80)
    print(f"Total prospects checked: {completed_count}")
    print(f"✅ RSS feeds found: {stats['found']} ({stats['found']/completed_count*100:.1f}% of checked)" if completed_count > 0 else "✅ RSS feeds found: 0")
    print(f"❌ Not found: {stats['not_found']}")
    print(f"⏱️  Time taken: {elapsed_time/60:.1f} minutes")
    if elapsed_time > 0:
        print(f"⚡ Rate: {completed_count/elapsed_time:.1f} prospects/second")
    print(f"\nDiscovery methods:")
    print(f"  Autodiscovery: {stats['methods']['autodiscovery']}")
    print(f"  URL patterns: {stats['methods']['pattern']}")
    print(f"  Sitemap: {stats['methods']['sitemap']}")
    print("=" * 80)

    if stats['found'] > 0:
        print(f"\n✅ {stats['found']} results saved to: {OUTPUT_FILE}")
        print(f"💡 Results were saved incrementally - no data lost!")
    else:
        print(f"\n⚠️  No new feeds discovered in this run")

if __name__ == '__main__':
    main()
