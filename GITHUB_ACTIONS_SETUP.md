# GitHub Actions Setup Guide

This guide will help you set up automated scraping using GitHub Actions.

## Step 1: Push Code to GitHub

First, push this repository to GitHub if you haven't already:

```bash
# Initialize git if needed
git init
git add .
git commit -m "Initial commit"

# Add your GitHub repository as remote
git remote add origin https://github.com/YOUR_USERNAME/scraping-service-outreach.git
git push -u origin main
```

## Step 2: Configure GitHub Secrets

Go to your GitHub repository settings and add these secrets:

**Settings → Secrets and variables → Actions → New repository secret**

Add the following secrets:

### Required Secrets:

1. **FIRECRAWL_API_KEY**
   - Your Firecrawl API key
   - Get it from: https://firecrawl.dev

2. **GH_PAT** (GitHub Personal Access Token)
   - Your GitHub token for pushing to the Pages repo
   - Get it from: https://github.com/settings/tokens/new
   - Required scopes: `repo`, `workflow`
   - Note: Use `GH_PAT` not `GITHUB_TOKEN` to avoid conflicts

3. **GITHUB_USERNAME**
   - Your GitHub username (e.g., `swelbyboy`)

4. **GITHUB_REPO_NAME**
   - Your GitHub Pages repository name (e.g., `prospect-rss-feeds`)

## Step 3: Verify Workflow File

The workflow file is located at: `.github/workflows/scrape-prospects.yml`

It's configured to:
- Run daily at 2 AM UTC
- Allow manual triggering from GitHub Actions tab

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

### Workflow fails with authentication error:
- Check that `GH_PAT` secret is set correctly
- Verify the token has `repo` and `workflow` scopes

### Workflow fails with Firecrawl error:
- Check `FIRECRAWL_API_KEY` is correct
- Verify your Firecrawl account has available credits

### No feeds published:
- Check the workflow logs for errors
- Verify `GITHUB_USERNAME` and `GITHUB_REPO_NAME` are correct
- Ensure the GitHub Pages repository exists

## View Results

- **Dashboard**: https://swelbyboy.github.io/prospect-rss-feeds/
- **Workflow runs**: Repository → Actions tab
- **Tracking data**: Check `tracking.csv` in your repo after each run
