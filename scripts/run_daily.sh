#!/bin/bash

REPO_DIR="/root/prospect-rss-feeds"
LOG_FILE="/root/logs/rss_update.log"
LOCK_FILE="/tmp/rss_update.lock"
MAX_DAILY_PROSPECTS="${MAX_DAILY_PROSPECTS:-12000}"

mkdir -p /root/logs

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    echo "$(date -u): Another run is already in progress (lock: $LOCK_FILE). Exiting." | tee -a "$LOG_FILE"
    exit 0
fi
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

cd "$REPO_DIR"
echo "=== RSS Update started at $(date -u) ===" | tee -a "$LOG_FILE"

# Stash any unstaged changes (e.g. tracking.csv from a previous interrupted run)
git stash >> "$LOG_FILE" 2>&1 || true

# Pull latest changes
git pull --rebase origin main >> "$LOG_FILE" 2>&1 || echo "WARNING: git pull failed, continuing with local version" | tee -a "$LOG_FILE"

# Activate venv
source venv/bin/activate

# Build prospects_update.csv sorted by staleness (oldest last_scrape_date first)
# This ensures the most out-of-date feeds are always refreshed first
python3 -c "
import csv, sys, os
from datetime import datetime
sys.path.insert(0, 'scripts')
from config import Config

epoch = datetime(1970, 1, 1)
max_daily = int(os.environ.get('MAX_DAILY_PROSPECTS', '5000'))

# Load last scrape dates from tracking.csv
last_scraped = {}
try:
    with open(Config.TRACKING_CSV) as f:
        for row in csv.DictReader(f):
            d = row.get('domain', '')
            date_str = row.get('last_scrape_date', '')
            if d and date_str:
                try:
                    last_scraped[d] = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass
except FileNotFoundError:
    pass

# Load original RSS URLs
orig = {}
with open(Config.DISCOVERY_RESULTS_CSV) as f:
    for row in csv.DictReader(f):
        if row.get('feed_url', '').strip():
            orig[row['domain']] = row['feed_url']

# Build prospect rows with original RSS URLs
rows = []
with open(Config.PROSPECTS_CSV) as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        if row.get('domain', '') in orig:
            row['rss_feed'] = orig[row['domain']]
            rows.append(row)

# Sort by staleness: never-scraped first, then oldest scrape date
rows.sort(key=lambda r: last_scraped.get(r.get('domain', ''), epoch))
rows = rows[:max_daily]

with open('/tmp/prospects_update.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
print(f'Generated {len(rows)} prospects sorted by staleness (limit: {max_daily})')
" MAX_DAILY_PROSPECTS="$MAX_DAILY_PROSPECTS" >> "$LOG_FILE" 2>&1

# ── Push to gh-pages function ────────────────────────────────────────────────
push_to_ghpages() {
    local FEED_COUNT
    FEED_COUNT=$(ls feeds/*.xml 2>/dev/null | wc -l)
    [ "$FEED_COUNT" -eq 0 ] && return

    python3 scripts/generate_index.py >> "$LOG_FILE" 2>&1

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
        git push origin HEAD:gh-pages >> "$LOG_FILE" 2>&1 && \
            echo "Published $FEED_COUNT feeds to gh-pages" | tee -a "$LOG_FILE" || \
            echo "WARNING: gh-pages push failed" | tee -a "$LOG_FILE"
    fi
    cd "$REPO_DIR"
    git worktree remove --force gh-pages-dir 2>/dev/null || true
}

# ── Run scraper in background ────────────────────────────────────────────────
PROSPECTS_CSV=/tmp/prospects_update.csv PARALLEL_WORKERS=20 SKIP_OG_DATA=true \
    python3 scripts/scraper.py >> "$LOG_FILE" 2>&1 &
SCRAPER_PID=$!
echo "Scraper started (PID $SCRAPER_PID)" | tee -a "$LOG_FILE"

# Push every 30 minutes while scraper is running
while kill -0 "$SCRAPER_PID" 2>/dev/null; do
    sleep 1800
    if kill -0 "$SCRAPER_PID" 2>/dev/null; then
        echo "--- Incremental push at $(date -u) ---" | tee -a "$LOG_FILE"
        push_to_ghpages
    fi
done
wait "$SCRAPER_PID"
echo "Scraper finished at $(date -u)" | tee -a "$LOG_FILE"

# ── Commit tracking data to main ─────────────────────────────────────────────
git add prospects/tracking.csv prospects/prospects.csv index.html 2>/dev/null || true
if git diff --staged --quiet; then
    echo "No tracking changes to commit" | tee -a "$LOG_FILE"
else
    git commit -m "Update RSS feeds - $(date -u '+%Y-%m-%d %H:%M:%S UTC')" >> "$LOG_FILE" 2>&1
    git pull --rebase origin main >> "$LOG_FILE" 2>&1 || true
    git push >> "$LOG_FILE" 2>&1 || echo "WARNING: git push failed" | tee -a "$LOG_FILE"
    echo "Committed tracking data" | tee -a "$LOG_FILE"
fi

# ── Final push ────────────────────────────────────────────────────────────────
echo "--- Final push at $(date -u) ---" | tee -a "$LOG_FILE"
push_to_ghpages

echo "=== RSS Update finished at $(date -u) ===" | tee -a "$LOG_FILE"
