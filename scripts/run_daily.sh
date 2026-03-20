#!/bin/bash
set -e

REPO_DIR="/root/prospect-rss-feeds"
LOG_FILE="/root/logs/rss_update.log"

cd "$REPO_DIR"

echo "=== RSS Update started at $(date -u) ===" | tee -a "$LOG_FILE"

# Pull latest changes
git pull origin main >> "$LOG_FILE" 2>&1

# Activate venv
source venv/bin/activate

# Clear local feeds so scraper re-fetches from original RSS URLs (not cached GitHub Pages copies)
rm -f feeds/*.xml

# Run the RSS update pipeline
PARALLEL_WORKERS=100 SKIP_OG_DATA=true python3 scripts/scraper.py >> "$LOG_FILE" 2>&1

# Commit tracking data to main
git add prospects/tracking.csv prospects/prospects.csv index.html 2>/dev/null || true
if git diff --staged --quiet; then
    echo "No tracking changes to commit" | tee -a "$LOG_FILE"
else
    git commit -m "Update RSS feeds - $(date -u '+%Y-%m-%d %H:%M:%S UTC')" >> "$LOG_FILE" 2>&1
    git pull --rebase origin main >> "$LOG_FILE" 2>&1
    git push >> "$LOG_FILE" 2>&1
    echo "Committed tracking data" | tee -a "$LOG_FILE"
fi

# Push XML feeds to gh-pages
if ls feeds/*.xml 1>/dev/null 2>&1; then
    FEED_COUNT=$(ls feeds/*.xml | wc -l)
    echo "Deploying $FEED_COUNT feeds to gh-pages" | tee -a "$LOG_FILE"

    git fetch origin gh-pages >> "$LOG_FILE" 2>&1

    # Remove existing worktree if it exists
    git worktree remove --force gh-pages-dir 2>/dev/null || true
    rm -rf gh-pages-dir

    if git ls-remote --exit-code origin gh-pages > /dev/null 2>&1; then
        git worktree add gh-pages-dir origin/gh-pages >> "$LOG_FILE" 2>&1
    else
        git worktree add --orphan -b gh-pages gh-pages-dir >> "$LOG_FILE" 2>&1
    fi

    cp feeds/*.xml gh-pages-dir/
    touch gh-pages-dir/.nojekyll

    cd gh-pages-dir
    git config user.name "VPS Bot"
    git config user.email "actions@github.com"
    git add .
    if git diff --staged --quiet; then
        echo "No feed changes to publish" | tee -a "$LOG_FILE"
    else
        git commit -m "Deploy feeds - $(date -u '+%Y-%m-%d %H:%M:%S UTC')" >> "$LOG_FILE" 2>&1
        git push origin HEAD:gh-pages >> "$LOG_FILE" 2>&1
        echo "Published $FEED_COUNT feeds to gh-pages" | tee -a "$LOG_FILE"
    fi
    cd "$REPO_DIR"
    git worktree remove --force gh-pages-dir 2>/dev/null || true
else
    echo "No XML feeds generated" | tee -a "$LOG_FILE"
fi

echo "=== RSS Update finished at $(date -u) ===" | tee -a "$LOG_FILE"
