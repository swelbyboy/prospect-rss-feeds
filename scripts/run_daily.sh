#!/bin/bash

REPO_DIR="/root/prospect-rss-feeds"
LOG_FILE="/root/logs/rss_update.log"

mkdir -p /root/logs
cd "$REPO_DIR"

echo "=== RSS Update started at $(date -u) ===" | tee -a "$LOG_FILE"

# Stash any unstaged changes (e.g. tracking.csv from a previous interrupted run)
git stash >> "$LOG_FILE" 2>&1 || true

# Pull latest changes (rebase to avoid divergent branch errors)
git pull --rebase origin main >> "$LOG_FILE" 2>&1 || echo "WARNING: git pull failed, continuing with local version" | tee -a "$LOG_FILE"

# Activate venv
source venv/bin/activate

# Build a temp prospects CSV using original RSS URLs from discovery results.
# This bypasses scraper.py's "skip if already processed" logic.
# Existing feeds/*.xml are kept — new articles merge with them (max 15 per feed),
# and failed fetches fall back to the previous content.
python3 -c "
import csv, sys
sys.path.insert(0, 'scripts')
from config import Config

orig = {}
with open(Config.DISCOVERY_RESULTS_CSV) as f:
    for row in csv.DictReader(f):
        if row.get('feed_url','').strip():
            orig[row['domain']] = row['feed_url']

rows = []
with open(Config.PROSPECTS_CSV) as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        if row.get('domain','') in orig:
            row['rss_feed'] = orig[row['domain']]
            rows.append(row)

with open('/tmp/prospects_update.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
print(f'Generated {len(rows)} prospects with original RSS URLs')
" >> "$LOG_FILE" 2>&1

# Run the RSS update pipeline
PROSPECTS_CSV=/tmp/prospects_update.csv PARALLEL_WORKERS=20 SKIP_OG_DATA=true python3 scripts/scraper.py >> "$LOG_FILE" 2>&1

# Regenerate index.html with updated tracking data (includes Domain column)
python3 scripts/generate_index.py >> "$LOG_FILE" 2>&1

# Commit tracking data to main
git add prospects/tracking.csv prospects/prospects.csv index.html 2>/dev/null || true
if git diff --staged --quiet; then
    echo "No tracking changes to commit" | tee -a "$LOG_FILE"
else
    git commit -m "Update RSS feeds - $(date -u '+%Y-%m-%d %H:%M:%S UTC')" >> "$LOG_FILE" 2>&1
    git pull --rebase origin main >> "$LOG_FILE" 2>&1 || true
    git push >> "$LOG_FILE" 2>&1 || echo "WARNING: git push failed" | tee -a "$LOG_FILE"
    echo "Committed tracking data" | tee -a "$LOG_FILE"
fi

# Push XML feeds to gh-pages
if ls feeds/*.xml 1>/dev/null 2>&1; then
    FEED_COUNT=$(ls feeds/*.xml | wc -l)
    echo "Deploying $FEED_COUNT feeds to gh-pages" | tee -a "$LOG_FILE"

    git fetch origin gh-pages >> "$LOG_FILE" 2>&1

    git worktree remove --force gh-pages-dir 2>/dev/null || true
    rm -rf gh-pages-dir

    if git ls-remote --exit-code origin gh-pages > /dev/null 2>&1; then
        git worktree add gh-pages-dir origin/gh-pages >> "$LOG_FILE" 2>&1
    else
        git worktree add --orphan -b gh-pages gh-pages-dir >> "$LOG_FILE" 2>&1
    fi

    cp feeds/*.xml gh-pages-dir/
    cp index.html gh-pages-dir/
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
