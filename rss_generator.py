"""
RSS feed generator module.
Creates RFC-compliant RSS 2.0 feeds for scraped articles.
"""

import os
from datetime import datetime, timezone
from feedgen.feed import FeedGenerator
from config import Config


class RSSFeedGenerator:
    """Generates RSS feeds for prospect articles."""

    def __init__(self):
        """Initialize the RSS feed generator."""
        os.makedirs(Config.FEEDS_DIR, exist_ok=True)

    def create_feed(self, prospect_data, articles):
        """
        Create an RSS feed for a prospect's articles.

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

        Returns:
            str: Path to the generated RSS feed file
        """
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
            fe.title(article['title'])
            fe.link(href=article['link'])

            # Set description
            description = article.get('description', '')
            if description:
                fe.description(description)
            else:
                fe.description(article['title'])

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
