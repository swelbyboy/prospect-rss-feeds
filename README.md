# 🔍 Prospect Article Scraping & RSS Feed Service

Automatically scrape articles from prospect websites and generate RSS feeds hosted on GitHub Pages.

## 📋 Overview

This service:
- Scrapes up to 10 articles from each prospect's website
- Generates individual RSS feeds per prospect
- Publishes feeds to GitHub Pages
- Tracks scraping success/failure in CSV
- Designed to run weekly (or on any schedule)
- **Now supports automated execution via GitHub Actions!**

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.8 or higher
- Git installed
- GitHub account
- Firecrawl API key ([get one here](https://www.firecrawl.dev/))

### 2. Installation

```bash
# Clone or navigate to this directory
cd scraping-service-outreach

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

1. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your credentials:**
   ```bash
   # Firecrawl API
   FIRECRAWL_API_KEY=fc-your_api_key_here

   # GitHub Configuration (for local runs only)
   GITHUB_TOKEN=ghp_your_github_token_here
   GITHUB_USERNAME=your_github_username
   GITHUB_REPO_NAME=prospect-rss-feeds
   ```

3. **For GitHub Actions:** Configure the `FIRECRAWL_API_KEY` secret in your repository settings (see [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md))

### 4. Set Up GitHub Pages Repository

**Option A: Via GitHub Web Interface**
1. Go to https://github.com/new
2. Repository name: `prospect-rss-feeds` (or match your `GITHUB_REPO_NAME`)
3. Make it **Public** (required for free GitHub Pages)
4. Click "Create repository"
5. Go to Settings > Pages
6. Source: Deploy from a branch
7. Branch: `main`, Folder: `/` (root)
8. Click Save

**Option B: Via Command Line**
```bash
# Create repository using GitHub CLI (if you have 'gh' installed)
gh repo create prospect-rss-feeds --public
```

### 5. Add Your Prospects

Edit `prospects.csv` with your prospect information:

```csv
id,company_name,domain
1,TechCorp,techcorp.com
2,InnovateLabs,innovatelabs.io
3,DataSystems,datasystems.net
```

- **id**: Unique identifier
- **company_name**: Company name (used in feed titles)
- **domain**: Website domain (without http/https)

### 6. Run the Scraper

**Option A: Run Locally**
```bash
python scraper.py
```

**Option B: Use GitHub Actions (Recommended)**
- The scraper runs automatically daily at 2 AM UTC
- Or trigger manually from the Actions tab in GitHub
- See [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) for setup instructions

The scraper will:
1. Load prospects from `prospects.csv`
2. Scrape each website for articles
3. Generate RSS feeds in the `feeds/` directory
4. Publish feeds to GitHub Pages
5. Update `tracking.csv` with results

## 📊 Output

### RSS Feeds
Feeds will be available at:
```
https://{username}.github.io/{repo_name}/{company-name}.xml
```

For example:
```
https://johndoe.github.io/prospect-rss-feeds/techcorp.xml
```

### Index Page
View all feeds at:
```
https://{username}.github.io/{repo_name}/
```

### Tracking Data
Check `tracking.csv` for scraping results:
- Scrape date and time
- Success/failure status
- Number of articles found
- RSS feed URL
- Error messages (if any)

## ⏰ Scheduling (Weekly Runs)

### GitHub Actions (Recommended)

The scraper is configured to run automatically via GitHub Actions:
- **Schedule**: Daily at 2 AM UTC
- **Manual trigger**: Available from GitHub Actions tab
- **Zero hosting costs**: Uses GitHub's free tier
- See [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) for setup

### macOS/Linux (cron - Alternative)

1. Open crontab:
   ```bash
   crontab -e
   ```

2. Add this line (runs every Monday at 9 AM):
   ```cron
   0 9 * * 1 cd /Users/samwelbank/Documents/scraping-service-outreach && /usr/bin/python3 scraper.py >> scraper.log 2>&1
   ```

3. Adjust the path and timing as needed

### Windows (Task Scheduler - Alternative)

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Weekly, Monday, 9:00 AM
4. Action: Start a program
   - Program: `python.exe`
   - Arguments: `scraper.py`
   - Start in: `C:\path\to\scraping-service-outreach`

## 🔧 Project Structure

```
scraping-service-outreach/
├── scraper.py              # Main orchestrator
├── rss_generator.py        # RSS feed generation
├── github_publisher.py     # GitHub Pages publishing
├── config.py               # Configuration management
├── prospects.csv           # Input: prospect list
├── tracking.csv            # Output: scraping results
├── requirements.txt        # Python dependencies
├── .env                    # Your credentials (not committed)
├── .env.example            # Template for .env
├── .gitignore              # Git ignore rules
├── .github/
│   └── workflows/
│       └── scrape-prospects.yml  # GitHub Actions workflow
├── GITHUB_ACTIONS_SETUP.md # GitHub Actions setup guide
└── README.md               # This file
```

## 🛠️ How It Works

### Article Detection

The scraper identifies articles by:
- URL patterns (`/blog/`, `/news/`, `/article/`, `/post/`, etc.)
- OpenGraph metadata (`og:type` = article, blog, news)
- Page metadata (publish dates, article tags)

### RSS Feed Format

Generates standard RSS 2.0 feeds with:
- Feed title: `{Company Name} - Article Feed`
- Feed link: Company website
- Items: Up to 10 latest articles
- Item details: title, link, description, publish date

### Error Handling

- Gracefully handles scraping failures
- Logs errors to `tracking.csv`
- Continues processing remaining prospects
- Retries with timeout protection

## 🔍 Troubleshooting

### "Configuration Warning" on first run
**Solution:** Copy `.env.example` to `.env` and add your API keys

### "Repository not found" error
**Solution:** Create the GitHub Pages repository first (see Setup step 4)

### "No articles found" for a prospect
**Possible causes:**
- Website doesn't have a blog/news section
- Articles use non-standard URL patterns
- Website blocks automated scraping

**Solution:** Check the website manually and verify it has articles

### Firecrawl API errors
**Possible causes:**
- Invalid API key
- Rate limit exceeded
- Website blocking Firecrawl

**Solution:** Check your Firecrawl dashboard for usage and errors

### GitHub Actions workflow not running
**Solution:** Check [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) for troubleshooting steps

## 📝 Customization

### Change article limit
Edit `.env`:
```bash
MAX_ARTICLES_PER_PROSPECT=20
```

Or set in GitHub Actions workflow environment variables.

### Modify article detection
Edit the `article_indicators` list in `scraper.py:141`:
```python
article_indicators = [
    '/blog/', '/news/', '/article/', '/insights/',
    '/your-custom-path/'
]
```

### Custom GitHub Pages domain
Edit `.env`:
```bash
CUSTOM_DOMAIN=feeds.yourdomain.com
```

Then configure your domain in GitHub Pages settings.

## 🔐 Security Notes

- Never commit `.env` to version control (already in `.gitignore`)
- Use GitHub tokens with minimal required permissions
- Rotate API keys periodically
- Keep dependencies updated: `pip install -r requirements.txt --upgrade`
- Store secrets in GitHub Secrets (not in code)

## 📚 Dependencies

- **firecrawl-py**: Web scraping via Firecrawl API
- **feedgen**: RFC-compliant RSS feed generation
- **GitPython**: Git operations for publishing
- **python-dotenv**: Environment variable management
- **pandas**: CSV data handling

## 🤝 Support

For issues with:
- **Firecrawl**: https://docs.firecrawl.dev/
- **GitHub Pages**: https://docs.github.com/pages
- **GitHub Actions**: https://docs.github.com/actions
- **This script**: Check `tracking.csv` for error messages

## 📄 License

This project is open source and available for personal and commercial use.

---

**Happy scraping!** 🎉
