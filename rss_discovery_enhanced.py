#!/usr/bin/env python3
"""
Enhanced RSS Feed Discovery Script
Discovers RSS feeds using multiple strategies:
1. Common RSS URL patterns (expanded list)
2. HTML autodiscovery via <link> tags
3. Sitemap.xml checking
4. Content-based detection
"""

import csv
import requests
import time
from urllib.parse import urljoin
import feedparser
from bs4 import BeautifulSoup
import re

# Expanded RSS feed URL patterns
RSS_PATTERNS = [
    # Standard WordPress
    '/feed',
    '/feed/',
    '/rss',
    '/rss/',
    '/feed.xml',
    '/rss.xml',
    '/atom.xml',

    # Blog-specific
    '/blog/feed',
    '/blog/feed/',
    '/blog/rss',
    '/blog/rss.xml',
    '/blog/atom.xml',

    # News-specific
    '/news/feed',
    '/news/rss',
    '/news/feed.xml',

    # Articles
    '/articles/feed',
    '/articles/rss',

    # Blogger/Google
    '/feeds/posts/default',
    '/feeds/posts/default?alt=rss',

    # Other common patterns
    '/index.rss',
    '/index.xml',
    '/main.rss',
    '/site.rss',
    '/feed.rss',
    '/.rss',
    '/rss.php',
    '/feed.php',

    # Category/section feeds
    '/category/news/feed',
    '/section/news/feed',
]

def check_autodiscovery(domain, timeout=2):
    """
    Check HTML <link> tags for RSS autodiscovery.

    Returns:
        tuple: (success, feed_url, error_message)
    """
    for scheme in ['https', 'http']:
        base_url = f"{scheme}://{domain}"

        try:
            response = requests.get(base_url, timeout=timeout,
                                   headers={'User-Agent': 'Mozilla/5.0'})

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for RSS/Atom autodiscovery links
                link_tags = soup.find_all('link', {
                    'rel': lambda x: x and ('alternate' in x.lower()),
                    'type': lambda x: x and ('rss' in x.lower() or 'atom' in x.lower() or 'xml' in x.lower())
                })

                for link in link_tags:
                    href = link.get('href')
                    if href:
                        # Make absolute URL
                        feed_url = urljoin(base_url, href)

                        # Verify it's a valid feed
                        feed = feedparser.parse(feed_url)
                        if feed.entries and len(feed.entries) > 0:
                            return (True, feed_url, None)

        except Exception as e:
            continue

    return (False, None, "No autodiscovery link found")


def check_sitemap(domain, timeout=1):
    """
    Check sitemap.xml for RSS feed references.

    Returns:
        tuple: (success, feed_url, error_message)
    """
    for scheme in ['https', 'http']:
        sitemap_urls = [
            f"{scheme}://{domain}/sitemap.xml",
            f"{scheme}://{domain}/sitemap_index.xml",
            f"{scheme}://{domain}/sitemap.xml.gz",
        ]

        for sitemap_url in sitemap_urls:
            try:
                response = requests.get(sitemap_url, timeout=timeout)
                if response.status_code == 200:
                    # Look for RSS feed URLs in sitemap
                    content = response.text

                    # Search for feed URLs
                    feed_matches = re.findall(r'<loc>(.*?/(?:feed|rss|atom).*?)</loc>', content)

                    for feed_url in feed_matches:
                        # Verify it's a valid feed
                        feed = feedparser.parse(feed_url)
                        if feed.entries and len(feed.entries) > 0:
                            return (True, feed_url, None)

            except Exception:
                continue

    return (False, None, "No feed found in sitemap")


def check_common_patterns(domain, timeout=1):
    """
    Try common RSS feed URL patterns.

    Returns:
        tuple: (success, feed_url, error_message)
    """
    for scheme in ['https', 'http']:
        base_url = f"{scheme}://{domain}"

        for pattern in RSS_PATTERNS:
            feed_url = urljoin(base_url, pattern)

            try:
                # Make HEAD request first to check if URL exists
                response = requests.head(feed_url, timeout=timeout, allow_redirects=True,
                                        headers={'User-Agent': 'Mozilla/5.0'})

                # If HEAD succeeds or returns 405 (Method Not Allowed), try GET
                if response.status_code in [200, 405]:
                    # Parse the feed to verify it's valid
                    feed = feedparser.parse(feed_url)

                    # Check if feed has entries
                    if feed.entries and len(feed.entries) > 0:
                        return (True, feed_url, None)

            except Exception:
                continue

    return (False, None, "No feed found with common patterns")


def discover_rss_feed(domain, verbose=True):
    """
    Comprehensive RSS feed discovery using multiple strategies.

    Args:
        domain: Domain to check (e.g., 'example.com')
        verbose: Print discovery attempts

    Returns:
        tuple: (success, feed_url, method, error_message)
    """
    # Strategy 1: HTML Autodiscovery (most reliable)
    if verbose:
        print(f"      🔍 Checking autodiscovery...")
    success, feed_url, error = check_autodiscovery(domain)
    if success:
        if verbose:
            print(f"      ✅ Found via autodiscovery")
        return (True, feed_url, "autodiscovery", None)

    # Strategy 2: Common URL patterns (fast)
    if verbose:
        print(f"      🔍 Trying common patterns...")
    success, feed_url, error = check_common_patterns(domain)
    if success:
        if verbose:
            print(f"      ✅ Found via URL pattern")
        return (True, feed_url, "pattern", None)

    # Strategy 3: Sitemap.xml (less common but worth trying)
    if verbose:
        print(f"      🔍 Checking sitemap...")
    success, feed_url, error = check_sitemap(domain)
    if success:
        if verbose:
            print(f"      ✅ Found via sitemap")
        return (True, feed_url, "sitemap", None)

    return (False, None, None, "No RSS feed found with any method")


def main():
    print("🔍 Enhanced RSS Feed Discovery")
    print("=" * 80)

    # Read prospects without RSS feeds
    prospects = []
    with open('prospects.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('rss_feed', '').strip():
                prospects.append(row)

    print(f"📋 Found {len(prospects)} prospects without RSS feeds\n")

    if len(prospects) == 0:
        print("✅ All prospects already have RSS feeds!")
        return

    # Discovery results
    found = 0
    not_found = 0
    results = []
    methods = {'autodiscovery': 0, 'pattern': 0, 'sitemap': 0}

    for i, prospect in enumerate(prospects, 1):
        company_name = prospect['company_name']
        domain = prospect['domain']
        prospect_id = prospect['id']

        print(f"[{i}/{len(prospects)}] {company_name} ({domain})")

        success, feed_url, method, error = discover_rss_feed(domain, verbose=True)

        if success:
            found += 1
            methods[method] += 1
            results.append({
                'id': prospect_id,
                'company_name': company_name,
                'domain': domain,
                'feed_url': feed_url,
                'discovery_method': method
            })
        else:
            not_found += 1
            print(f"      ❌ {error}")

        # Rate limiting
        time.sleep(0.1)

        # Progress update every 25 prospects
        if i % 25 == 0:
            print(f"\n   Progress: {i}/{len(prospects)} | Found: {found} ({found/i*100:.1f}%) | Not found: {not_found}\n")

    print("\n" + "=" * 80)
    print("📊 DISCOVERY SUMMARY")
    print("=" * 80)
    print(f"Total prospects checked: {len(prospects)}")
    print(f"✅ RSS feeds found: {found} ({found/len(prospects)*100:.1f}%)")
    print(f"❌ Not found: {not_found} ({not_found/len(prospects)*100:.1f}%)")
    print(f"\nDiscovery methods:")
    print(f"  Autodiscovery: {methods['autodiscovery']}")
    print(f"  URL patterns: {methods['pattern']}")
    print(f"  Sitemap: {methods['sitemap']}")
    print("=" * 80)

    # Write results to CSV
    if results:
        with open('rss_discovery_results_enhanced.csv', 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'company_name', 'domain', 'feed_url', 'discovery_method'])
            writer.writeheader()
            writer.writerows(results)

        print(f"\n✅ Results written to: rss_discovery_results_enhanced.csv")
        print(f"\n💡 Next: Run update script to add {len(results)} feeds to prospects.csv")
        print(f"   Then re-run the discovery workflow to update the feeds")
    else:
        print(f"\n⚠️  No new feeds discovered")

if __name__ == '__main__':
    main()
