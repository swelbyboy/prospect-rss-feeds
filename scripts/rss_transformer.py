#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSS Feed Transformer
Fetches RSS feeds from prospects and normalizes them into our standard format.
Includes deduplication logic to handle same article in multiple languages.
"""

import feedparser
import requests
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse
import re
import html


class RSSTransformer:
    """Transforms prospect RSS feeds into standardized article format."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; RSSTransformer/1.0)'
        })
        self._og_data_cache = {}  # Cache OG data lookups to avoid redundant requests
        self._skip_og_data = False  # Flag to skip OG data fetching for faster updates

    def fetch_feed(self, feed_url, max_articles=10):
        """
        Fetch and parse an RSS feed.

        Args:
            feed_url (str): URL of the RSS feed
            max_articles (int): Maximum number of articles to fetch

        Returns:
            tuple: (success: bool, articles: list, error_message: str)
        """
        import gc
        try:
            print(f"   📡 Fetching RSS feed: {feed_url}")
            response = self.session.get(feed_url, timeout=10, allow_redirects=True)

            if response.status_code != 200:
                response.close()
                return False, [], f"HTTP {response.status_code}"

            # Extract content and immediately free the response object
            content = response.content
            response.close()
            del response

            # Parse feed then free the raw content
            feed = feedparser.parse(content)
            del content

            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                del feed
                gc.collect()
                return False, [], "No entries found in feed"

            # Extract and normalize articles (copy only what we need)
            articles = []
            for entry in feed.entries[:max_articles]:
                article = self._normalize_entry(entry, feed_url)
                if article:
                    articles.append(article)

            entry_count = len(articles)
            del feed
            gc.collect()

            print(f"   ✅ Fetched {entry_count} articles from RSS feed")
            return True, articles, None

        except Exception as e:
            gc.collect()
            return False, [], f"Error fetching feed: {str(e)}"

    def _normalize_entry(self, entry, feed_url):
        """
        Normalize an RSS feed entry into our standard article format.
        Priority: OG data > RSS data

        Args:
            entry: feedparser entry object
            feed_url (str): Source feed URL

        Returns:
            dict: Normalized article data
        """
        try:
            # Extract link first (we need it for OG lookup)
            link = entry.get('link', '').strip()
            if not link:
                return None

            # Try to fetch Open Graph data first (PRIORITY)
            og_data = self._fetch_og_data(link)
            data_source = 'OG' if og_data else 'RSS'

            # Extract title - prioritize OG data
            title = og_data.get('title') if og_data else None
            if not title:
                title = entry.get('title', '').strip()
            if not title:
                return None
            
            # Decode HTML entities from title
            title = html.unescape(title)

            # Extract description - prioritize OG data
            description = og_data.get('description') if og_data else None
            if not description:
                if 'summary' in entry:
                    description = entry.summary
                elif 'description' in entry:
                    description = entry.description
                elif 'content' in entry and len(entry.content) > 0:
                    description = entry.content[0].get('value', '')

            # Clean HTML tags and entities from description
            description = self._clean_html(description)
            description = description[:500].strip()  # Limit length

            # Extract publication date (OG doesn't have this, use RSS)
            pub_date = None
            if 'published_parsed' in entry and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            elif 'updated_parsed' in entry and entry.updated_parsed:
                pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

            if not pub_date:
                pub_date = datetime.now(timezone.utc)

            # Extract image - prioritize OG data
            image_url = og_data.get('image') if og_data else None
            if not image_url:
                image_url = self._extract_image(entry)

            # Create unique GUID
            guid = entry.get('id') or entry.get('guid') or link

            # Extract language if available
            language = self._extract_language(entry, feed_url)

            return {
                'title': title,
                'link': link,
                'description': description,
                'pub_date': pub_date,
                'image_url': image_url,
                'guid': guid,
                'language': language,
                'data_source': data_source,  # Track whether we used OG or RSS data
                # For deduplication
                'content_hash': self._generate_content_hash(title, description)
            }

        except Exception as e:
            print(f"   ⚠️  Error normalizing entry: {e}")
            return None

    def _clean_html(self, text):
        """Remove HTML tags and decode ALL HTML entities."""
        if not text:
            return ''

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Decode ALL HTML entities (handles &#038;, &hellip;, &#8217;, etc.)
        text = html.unescape(text)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _fetch_og_data(self, url):
        """
        Fetch Open Graph data (title, description, image) from an article URL.

        Args:
            url (str): Article URL

        Returns:
            dict: Dictionary with 'title', 'description', 'image' or None if failed
        """
        # Skip OG data fetching if flag is set (for faster updates)
        if self._skip_og_data:
            return None

        # Check cache first
        if url in self._og_data_cache:
            return self._og_data_cache[url]

        try:
            # Fetch the article page with a shorter timeout
            response = self.session.get(url, timeout=10, allow_redirects=True)

            if response.status_code != 200:
                self._og_data_cache[url] = None
                return None

            og_data = {}

            # Look for og:title
            title_patterns = [
                r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
                r'<meta[^>]+name=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']og:title["\']',
            ]

            for pattern in title_patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    # Decode HTML entities from OG title
                    og_data['title'] = html.unescape(match.group(1))
                    break

            # Look for og:description
            desc_patterns = [
                r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
                r'<meta[^>]+name=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']og:description["\']',
            ]

            for pattern in desc_patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    # Decode HTML entities from OG description
                    og_data['description'] = html.unescape(match.group(1))
                    break

            # Look for og:image
            image_patterns = [
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                r'<meta[^>]+name=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']og:image["\']',
            ]

            for pattern in image_patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    og_data['image'] = match.group(1)
                    break

            # Only return og_data if we found at least one field
            if og_data:
                self._og_data_cache[url] = og_data
                return og_data

            # No OG data found
            self._og_data_cache[url] = None
            return None

        except Exception as e:
            print(f"   ⚠️  Could not fetch OG data from {url[:50]}...: {e}")
            self._og_data_cache[url] = None
            return None

    def _extract_image(self, entry):
        """
        Extract image URL from RSS entry.

        Args:
            entry: feedparser entry object

        Returns:
            str: Image URL or None
        """
        # Try media:thumbnail first (most common, used by Wired, etc.)
        if 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
            return entry.media_thumbnail[0].get('url')

        # Try enclosure
        if 'enclosures' in entry and len(entry.enclosures) > 0:
            for enclosure in entry.enclosures:
                # Check for image type or any URL ending in image extension
                enclosure_type = enclosure.get('type', '')
                enclosure_url = enclosure.get('href') or enclosure.get('url', '')

                if enclosure_type.startswith('image/'):
                    return enclosure_url

                # Also accept if URL looks like an image
                if enclosure_url and any(enclosure_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    return enclosure_url

        # Try media:content
        if 'media_content' in entry and len(entry.media_content) > 0:
            for media in entry.media_content:
                if media.get('type', '').startswith('image/'):
                    return media.get('url')

        # Try to extract from HTML content/summary
        for field in ['content', 'summary']:
            if field in entry:
                html_content = ''
                if field == 'content' and len(entry.content) > 0:
                    html_content = entry.content[0].get('value', '')
                else:
                    html_content = entry.get(field, '')

                if html_content:
                    # Look for first img tag
                    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
                    if img_match:
                        return img_match.group(1)

        return None

    def _extract_language(self, entry, feed_url):
        """
        Extract language from entry or infer from URL.

        Args:
            entry: feedparser entry object
            feed_url (str): Feed URL

        Returns:
            str: Language code (e.g., 'en', 'fr', 'es')
        """
        # Try entry language
        if 'language' in entry:
            return entry.language[:2].lower()

        # Get the article URL
        article_url = entry.get('link', '')
        combined_url = feed_url + article_url

        # Check for language-specific URL patterns
        language_patterns = {
            'es': [r'/espanol/', r'/español/', r'/es/', r'/spanish/'],
            'fr': [r'/francais/', r'/français/', r'/fr/', r'/french/'],
            'de': [r'/deutsch/', r'/de/', r'/german/'],
            'pt': [r'/portugues/', r'/português/', r'/pt/', r'/portuguese/'],
            'it': [r'/italiano/', r'/it/', r'/italian/'],
            'ja': [r'/japanese/', r'/jp/', r'/ja/'],
            'zh': [r'/chinese/', r'/cn/', r'/zh/'],
        }

        # Check each language pattern
        for lang_code, patterns in language_patterns.items():
            for pattern in patterns:
                if re.search(pattern, combined_url, re.IGNORECASE):
                    return lang_code

        # Try generic two-letter language codes: /xx/
        match = re.search(r'/([a-z]{2})/', combined_url)
        if match:
            return match.group(1).lower()

        # Default to English
        return 'en'

    def _generate_content_hash(self, title, description):
        """
        Generate a hash of article content for deduplication.

        Args:
            title (str): Article title
            description (str): Article description

        Returns:
            str: Hash of content
        """
        # Normalize text for comparison
        text = f"{title} {description}".lower()
        text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace

        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def filter_by_language(self, articles, keep_language='en'):
        """
        Filter articles to only keep specified language.

        Args:
            articles (list): List of article dictionaries
            keep_language (str): Language code to keep (e.g., 'en')

        Returns:
            list: Filtered articles
        """
        filtered = []
        excluded_count = 0

        for article in articles:
            article_lang = article.get('language', 'en')
            
            # Keep if it matches the desired language
            if article_lang == keep_language:
                filtered.append(article)
            else:
                excluded_count += 1
                print(f"   🚫 Excluded {article_lang} article: {article['title'][:50]}...")

        if excluded_count > 0:
            print(f"   🌐 Filtered out {excluded_count} non-{keep_language} article(s)")

        return filtered

    def deduplicate_articles(self, articles, keep_language='en'):
        """
        Remove duplicate articles, preferring specified language.

        Args:
            articles (list): List of article dictionaries
            keep_language (str): Preferred language code

        Returns:
            list: Deduplicated articles
        """
        seen_hashes = {}
        unique_articles = []

        for article in articles:
            content_hash = article.get('content_hash')

            if content_hash not in seen_hashes:
                # First time seeing this content
                seen_hashes[content_hash] = article
                unique_articles.append(article)
            else:
                # Duplicate found - keep preferred language
                existing = seen_hashes[content_hash]

                # Replace if this article is in preferred language and existing is not
                if article.get('language') == keep_language and existing.get('language') != keep_language:
                    # Remove old article and add new one
                    unique_articles.remove(existing)
                    unique_articles.append(article)
                    seen_hashes[content_hash] = article
                    print(f"   🔄 Replaced duplicate with {keep_language} version: {article['title'][:50]}...")

        removed_count = len(articles) - len(unique_articles)
        if removed_count > 0:
            print(f"   ♻️  Removed {removed_count} duplicate article(s)")

        return unique_articles

    def fetch_and_normalize(self, feed_url, max_articles=10, keep_language='en'):
        """
        Fetch RSS feed, normalize, filter by language, and deduplicate articles.

        Args:
            feed_url (str): URL of the RSS feed
            max_articles (int): Maximum number of articles to fetch
            keep_language (str): Preferred language code (e.g., 'en'). Articles in other languages will be excluded.

        Returns:
            tuple: (success: bool, articles: list, error_message: str)
        """
        # Fetch feed
        success, articles, error = self.fetch_feed(feed_url, max_articles)

        if not success:
            return False, [], error

        # Filter by language first
        articles = self.filter_by_language(articles, keep_language)

        # Then deduplicate
        articles = self.deduplicate_articles(articles, keep_language)

        return True, articles, None


def main():
    """Test the transformer with a sample feed."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python rss_transformer.py <feed_url>")
        sys.exit(1)

    feed_url = sys.argv[1]

    transformer = RSSTransformer()
    success, articles, error = transformer.fetch_and_normalize(feed_url, max_articles=10)

    if not success:
        print(f"❌ Error: {error}")
        sys.exit(1)

    print(f"\n📊 Found {len(articles)} unique articles:")
    print("="*80)

    for i, article in enumerate(articles, 1):
        print(f"\n{i}. {article['title']}")
        print(f"   Link: {article['link']}")
        print(f"   Date: {article['pub_date']}")
        print(f"   Language: {article['language']}")
        print(f"   Description: {article['description'][:100]}...")
        if article['image_url']:
            print(f"   Image: {article['image_url']}")


if __name__ == "__main__":
    main()
