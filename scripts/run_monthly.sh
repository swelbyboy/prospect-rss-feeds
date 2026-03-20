#!/bin/bash
set -e

REPO_DIR="/root/prospect-rss-feeds"
LOG_FILE="/root/logs/rss_discovery.log"

cd "$REPO_DIR"

echo "=== RSS Discovery started at $(date -u) ===" | tee -a "$LOG_FILE"

git pull origin main >> "$LOG_FILE" 2>&1

source venv/bin/activate

# Run discovery as a single chunk (no matrix needed on VPS)
TOTAL_CHUNKS=1 CHUNK_INDEX=0 GITHUB_CI=true python3 scripts/rss_discovery.py >> "$LOG_FILE" 2>&1

# Update prospects with discovered feeds
python3 scripts/update_prospects_with_discovered_feeds.py >> "$LOG_FILE" 2>&1
python3 scripts/establish_tracker_truth.py >> "$LOG_FILE" 2>&1

# Commit results
git add prospects/rss_discovery_results_enhanced.csv prospects/prospects.csv prospects/outreach_progress_tracker.csv 2>/dev/null || true
if git diff --staged --quiet; then
    echo "No discovery changes to commit" | tee -a "$LOG_FILE"
else
    git commit -m "RSS discovery results - $(date -u '+%Y-%m-%d')" >> "$LOG_FILE" 2>&1
    git pull --rebase origin main >> "$LOG_FILE" 2>&1
    git push >> "$LOG_FILE" 2>&1
    echo "Committed discovery results" | tee -a "$LOG_FILE"
fi

echo "=== RSS Discovery finished at $(date -u) ===" | tee -a "$LOG_FILE"
