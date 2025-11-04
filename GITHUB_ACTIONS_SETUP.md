# GitHub Actions Setup Guide

This guide will help you set up automated scraping using GitHub Actions.

## Step 1: Push Code to GitHub

Push this code to your existing GitHub Pages repository:

```bash
# Add your repository as remote
git remote add origin https://github.com/swelbyboy/prospect-rss-feeds.git

# Push the code
git push -u origin main
```

## Step 2: Configure GitHub Secret

Go to your GitHub repository settings and add this secret:

**Settings → Secrets and variables → Actions → New repository secret**

### Required Secret:

**FIRECRAWL_API_KEY**
- Your Firecrawl API key
- Get it from: https://firecrawl.dev

That's it! No other secrets needed - the workflow uses the built-in `GITHUB_TOKEN`.

## Step 3: Enable GitHub Pages

Make sure GitHub Pages is enabled:

1. Go to **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: **main** (root folder)
4. Click **Save**

Your dashboard will be at: https://swelbyboy.github.io/prospect-rss-feeds/

## Step 4: Test the Workflow

### Manual Test:
1. Go to your repository on GitHub
2. Click on "Actions" tab
3. Click "Scrape Prospect Articles" in the left sidebar
4. Click "Run workflow" button
5. Click "Run workflow" in the popup

### Monitor Progress:
- Watch the workflow run in real-time
- Check for any errors in the logs
- Verify feeds are published to GitHub Pages

## Step 5: Adjust Schedule (Optional)

Edit `.github/workflows/scrape-prospects.yml` to change the schedule:

```yaml
schedule:
  # Run daily at 2 AM UTC
  - cron: '0 2 * * *'
```

Common schedules:
- `0 2 * * *` - Daily at 2 AM UTC
- `0 */12 * * *` - Every 12 hours
- `0 2 * * 1` - Every Monday at 2 AM UTC
- `0 2 1 * *` - First day of each month at 2 AM UTC

## Adding New Prospects

To add new prospects:
1. Go to your repository on GitHub
2. Navigate to `prospects.csv`
3. Click the pencil icon (Edit)
4. Add new rows with: `id,company_name,domain`
5. Commit changes
6. The next scheduled run will scrape the new prospects

Or manually trigger a run immediately after adding prospects.

## Troubleshooting

### Workflow fails with permission error:
- Make sure the workflow has `contents: write` permission (already configured)
- Check that Actions are enabled in your repository settings

### Workflow fails with Firecrawl error:
- Check `FIRECRAWL_API_KEY` secret is correct
- Verify your Firecrawl account has available credits

### Dashboard not updating:
- Check that GitHub Pages is enabled and deploying from `main` branch
- Wait a few minutes for GitHub Pages to rebuild
- Check the workflow logs for commit/push errors

## View Results

- **Dashboard**: https://swelbyboy.github.io/prospect-rss-feeds/
- **Workflow runs**: Repository → Actions tab
- **Tracking data**: Check `tracking.csv` in your repo after each run

## Local Development

You can still run the scraper locally:

```bash
# Set up environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Copy .env.example to .env and fill in values
cp .env.example .env

# Run scraper
python scraper.py
```

When running locally, it will use the GitHub publisher to push to the repo as before.
