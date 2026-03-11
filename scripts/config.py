"""
Configuration module for the scraping service.
Loads settings from environment variables and provides default values.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root is the parent of this file's directory (scripts/)
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPTS_DIR)
_PROSPECTS_DIR = os.path.join(_PROJECT_ROOT, 'prospects')


class Config:
    """Application configuration."""

    # Project layout
    PROJECT_ROOT = _PROJECT_ROOT
    PROSPECTS_DIR = _PROSPECTS_DIR

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

    # File Paths — all absolute so scripts work from any working directory
    PROSPECTS_CSV = os.getenv('PROSPECTS_CSV', os.path.join(_PROSPECTS_DIR, 'prospects.csv'))
    TRACKING_CSV = os.path.join(_PROSPECTS_DIR, 'tracking.csv')
    OUTREACH_TRACKER_CSV = os.path.join(_PROSPECTS_DIR, 'outreach_progress_tracker.csv')
    DISCOVERY_RESULTS_CSV = os.path.join(_PROSPECTS_DIR, 'rss_discovery_results_enhanced.csv')
    CURRENT_FEEDS_TXT = os.path.join(_PROSPECTS_DIR, 'current_feeds.txt')
    MASTER_STATUS_CSV = os.path.join(_PROSPECTS_DIR, 'master_status.csv')
    INDEX_HTML = os.path.join(_PROJECT_ROOT, 'index.html')
    FEEDS_DIR = os.path.join(_PROJECT_ROOT, 'feeds')
    GITHUB_PAGES_DIR = os.path.join(_PROJECT_ROOT, 'github-pages-repo')

    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        errors = []
        is_ci = os.getenv('GITHUB_CI') == 'true'

        # Firecrawl API key is no longer required since we only use RSS feeds
        # Keeping the config for backwards compatibility but not validating
        
        # GitHub config is only required when not running in CI
        # (CI mode uses GitHub Actions workflow for commits)
        if not is_ci:
            if not cls.GITHUB_TOKEN:
                errors.append("GITHUB_TOKEN is not set (check .env file or environment variables)")

            if not cls.GITHUB_USERNAME:
                errors.append("GITHUB_USERNAME is not set (check .env file or environment variables)")

        if errors:
            raise ValueError(
                "Missing required configuration:\n" + "\n".join(f"- {e}" for e in errors)
            )

    @classmethod
    def get_rss_base_url(cls):
        """Get the base URL for RSS feeds on GitHub Pages."""
        if cls.CUSTOM_DOMAIN:
            return f"https://{cls.CUSTOM_DOMAIN}"
        
        # In CI mode, derive from GitHub Actions environment variables
        is_ci = os.getenv('GITHUB_CI') == 'true'
        if is_ci:
            # GitHub Actions provides GITHUB_REPOSITORY in format "username/repo"
            github_repo = os.getenv('GITHUB_REPOSITORY', 'swelbyboy/prospect-rss-feeds')
            username, repo_name = github_repo.split('/', 1) if '/' in github_repo else ('swelbyboy', 'prospect-rss-feeds')
            return f"https://{username}.github.io/{repo_name}"
        
        return f"https://{cls.GITHUB_USERNAME}.github.io/{cls.GITHUB_REPO_NAME}"


# Validate configuration when module is imported
try:
    Config.validate()
except ValueError as e:
    print(f"⚠️  Configuration Warning: {e}")
    print("Please copy .env.example to .env and fill in your API keys.")
