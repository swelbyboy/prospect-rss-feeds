#!/bin/bash
cd /root/prospect-rss-feeds
source venv/bin/activate

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
print(f'Generated {len(rows)} prospects')
"

MAX_PROSPECTS=10 PARALLEL_WORKERS=10 SKIP_OG_DATA=true PROSPECTS_CSV=/tmp/prospects_update.csv python3 scripts/scraper.py
