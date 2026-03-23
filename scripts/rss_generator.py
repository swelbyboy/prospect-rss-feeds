"""
RSS feed generator module.
Creates RFC-compliant RSS 2.0 feeds for scraped articles.
"""

import os
from datetime import datetime, timezone
from time import mktime
from feedgen.feed import FeedGenerator
from xml.sax.saxutils import escape
import feedparser
from config import Config


class RSSFeedGenerator:
    """Generates RSS feeds for prospect articles."""

    def __init__(self):
        """Initialize the RSS feed generator."""
        os.makedirs(Config.FEEDS_DIR, exist_ok=True)

    def _read_existing_articles(self, prospect_data):
        """Parse the existing local XML feed and return articles in standard format."""
        feed_path = self._get_feed_path(prospect_data)
        if not os.path.exists(feed_path):
            return []
        try:
            feed = feedparser.parse(feed_path)
            articles = []
            for entry in feed.entries:
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
                image_url = ''
                if hasattr(entry, 'enclosures') and entry.enclosures:
                    image_url = entry.enclosures[0].get('url', '')
                articles.append({
                    'link': entry.get('link', ''),
                    'title': entry.get('title', ''),
                    'description': entry.get('summary', ''),
                    'image_url': image_url,
                    'published_date': pub_date,
                })
            return articles
        except Exception:
            return []

    def create_feed(self, prospect_data, articles, max_articles=15):
        """
        Create an RSS feed for a prospect's articles, merging with any existing
        local feed. New articles take precedence; oldest articles are dropped
        once the total exceeds max_articles.

        Args:
            prospect_data (dict): Prospect information with keys:
                - id: Prospect ID
                - company_name: Company name
                - domain: Domain URL
            articles (list): List of article dictionaries with keys:
                - title: Article title
                - link: Article URL
                - description: Article description/summary
                - published_date: Published date (optional)
                - image_url: Article image URL (optional)
            max_articles (int): Maximum articles to keep (default 15)

        Returns:
            str: Path to the generated RSS feed file
        """
        # Merge new articles with existing, deduplicate by URL, cap at max_articles
        existing = self._read_existing_articles(prospect_data)
        seen = set()
        merged = []
        for a in articles + existing:
            link = a.get('link', '')
            if link and link not in seen:
                seen.add(link)
                merged.append(a)

        _epoch = datetime.fromtimestamp(0, tz=timezone.utc)

        def _sort_key(article):
            d = article.get('published_date') or _epoch
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d

        merged.sort(key=_sort_key, reverse=True)
        articles = merged[:max_articles]

        fg = FeedGenerator()

        # Set feed metadata
        company_name = prospect_data['company_name']
        domain = prospect_data['domain']
        feed_url = f"{Config.get_rss_base_url()}/{self._get_feed_filename(prospect_data)}"

        fg.id(feed_url)
        fg.title(f"{company_name} - Article Feed")
        fg.link(href=f"https://{domain}", rel='alternate')
        fg.link(href=feed_url, rel='self')
        fg.description(f"Latest articles from {company_name} ({domain})")
        fg.language('en')
        fg.generator('Prospect Scraping Service')
        fg.lastBuildDate(datetime.now(timezone.utc))

        # Add articles to feed
        for article in articles:
            fe = fg.add_entry()
            fe.id(article['link'])
            
            # Escape XML special characters in title and description
            # This ensures & becomes &amp;, < becomes &lt;, etc.
            title = escape(article['title'])
            fe.title(title)
            fe.link(href=article['link'])

            # Set description with XML escaping
            description = article.get('description', '')
            if description:
                fe.description(escape(description))
            else:
                fe.description(title)

            # Set image as enclosure if available
            image_url = article.get('image_url', '')
            if image_url:
                # Determine MIME type from URL extension
                mime_type = 'image/jpeg'  # default
                if image_url.lower().endswith('.png'):
                    mime_type = 'image/png'
                elif image_url.lower().endswith('.gif'):
                    mime_type = 'image/gif'
                elif image_url.lower().endswith('.webp'):
                    mime_type = 'image/webp'

                # Add enclosure (length 0 is acceptable when size is unknown)
                fe.enclosure(url=image_url, length='0', type=mime_type)

            # Set published date
            if 'published_date' in article and article['published_date']:
                try:
                    if isinstance(article['published_date'], str):
                        pub_date = datetime.fromisoformat(article['published_date'])
                    else:
                        pub_date = article['published_date']

                    # Ensure timezone info
                    if pub_date.tzinfo is None:
                        pub_date = pub_date.replace(tzinfo=timezone.utc)

                    fe.published(pub_date)
                except (ValueError, TypeError):
                    # If date parsing fails, use current time
                    fe.published(datetime.now(timezone.utc))
            else:
                fe.published(datetime.now(timezone.utc))

        # Generate RSS file
        feed_path = self._get_feed_path(prospect_data)
        fg.rss_file(feed_path, pretty=True)

        return feed_path

    def _get_feed_filename(self, prospect_data):
        """
        Generate a filename for the RSS feed.

        Args:
            prospect_data (dict): Prospect information

        Returns:
            str: Sanitized filename (e.g., 'techcorp.xml')
        """
        company_name = prospect_data['company_name']
        # Sanitize company name for filename
        safe_name = ''.join(c if c.isalnum() else '-' for c in company_name.lower())
        safe_name = safe_name.strip('-')
        return f"{safe_name}.xml"

    def _get_feed_path(self, prospect_data):
        """
        Get the full path for the RSS feed file.

        Args:
            prospect_data (dict): Prospect information

        Returns:
            str: Full path to feed file
        """
        filename = self._get_feed_filename(prospect_data)
        return os.path.join(Config.FEEDS_DIR, filename)

    def get_feed_url(self, prospect_data):
        """
        Get the public URL for a prospect's RSS feed.

        Args:
            prospect_data (dict): Prospect information

        Returns:
            str: Public RSS feed URL
        """
        filename = self._get_feed_filename(prospect_data)
        return f"{Config.get_rss_base_url()}/{filename}"


if __name__ == "__main__":
    # Test the RSS generator
    generator = RSSFeedGenerator()

    test_prospect = {
        'id': '1',
        'company_name': 'Test Company',
        'domain': 'example.com'
    }

    test_articles = [
        {
            'title': 'Test Article 1',
            'link': 'https://example.com/article-1',
            'description': 'This is a test article description.',
            'published_date': datetime.now(),
            'image_url': 'https://example.com/images/article-1.jpg'
        },
        {
            'title': 'Test Article 2',
            'link': 'https://example.com/article-2',
            'description': 'Another test article.',
            'published_date': datetime.now(),
            'image_url': 'https://example.com/images/article-2.png'
        }
    ]

    feed_path = generator.create_feed(test_prospect, test_articles)
    print(f"Test feed created: {feed_path}")
    print(f"Feed URL: {generator.get_feed_url(test_prospect)}")
