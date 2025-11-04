"""
Configuration module for the scraping service.
Loads settings from environment variables and provides default values.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # Firecrawl API Configuration
    FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')

    # GitHub Configuration
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
    GITHUB_REPO_NAME = os.getenv('GITHUB_REPO_NAME', 'prospect-rss-feeds')
    CUSTOM_DOMAIN = os.getenv('CUSTOM_DOMAIN')

    # Scraping Configuration
    MAX_ARTICLES_PER_PROSPECT = int(os.getenv('MAX_ARTICLES_PER_PROSPECT', 10))
    SCRAPING_TIMEOUT = int(os.getenv('SCRAPING_TIMEOUT', 60))

    # File Paths
    PROSPECTS_CSV = 'prospects_mini_test.csv'  # Using mini test file with 2 prospects
    TRACKING_CSV = 'tracking.csv'
    FEEDS_DIR = 'feeds'
    GITHUB_PAGES_DIR = 'github-pages-repo'

    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        errors = []

        if not cls.FIRECRAWL_API_KEY:
            errors.append("FIRECRAWL_API_KEY is not set in .env file")

        if not cls.GITHUB_TOKEN:
            errors.append("GITHUB_TOKEN is not set in .env file")

        if not cls.GITHUB_USERNAME:
            errors.append("GITHUB_USERNAME is not set in .env file")

        if errors:
            raise ValueError(
                "Missing required configuration:\n" + "\n".join(f"- {e}" for e in errors)
            )

    @classmethod
    def get_rss_base_url(cls):
        """Get the base URL for RSS feeds on GitHub Pages."""
        if cls.CUSTOM_DOMAIN:
            return f"https://{cls.CUSTOM_DOMAIN}"
        return f"https://{cls.GITHUB_USERNAME}.github.io/{cls.GITHUB_REPO_NAME}"


# Validate configuration when module is imported
try:
    Config.validate()
except ValueError as e:
    print(f"⚠️  Configuration Warning: {e}")
    print("Please copy .env.example to .env and fill in your API keys.")
