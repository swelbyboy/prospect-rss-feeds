# RSS Feed Discovery Improvement Guide

## Current Status
- **1,047 total prospects**
- **487 with RSS feeds (46%)**
- **560 without RSS feeds (54%)**

## Goal
Increase RSS feed discovery rate from 46% to 70%+ by using multiple strategies.

---

## Strategy 1: Enhanced RSS Discovery (READY TO USE)

### What it does:
Uses 3 methods to find RSS feeds:

1. **HTML Autodiscovery** (Most reliable)
   - Checks `<link rel="alternate">` tags in page headers
   - This is how browsers find RSS feeds
   - Success rate: ~30-40%

2. **Common URL Patterns** (Fast)
   - Tries 28 common RSS feed URLs
   - e.g., `/feed`, `/rss`, `/blog/feed`, etc.
   - Success rate: ~20-30%

3. **Sitemap.xml Checking** (Comprehensive)
   - Searches sitemap files for feed references
   - Success rate: ~5-10%

### How to run:

```bash
# Install required dependencies
pip install beautifulsoup4

# Run enhanced discovery on prospects without feeds
python3 rss_discovery_enhanced.py

# Update prospects.csv with discovered feeds
python3 update_prospects_with_discovered_feeds.py

# Commit the changes
git add prospects.csv
git commit -m "Add newly discovered RSS feeds"
git push
```

### Expected results:
- **Additional 100-150 feeds discovered** (bringing total to ~600-640 feeds)
- **Success rate: 60-65%**

---

## Strategy 2: Generate Synthetic Feeds (FOR SITES WITHOUT RSS)

For the remaining ~400 prospects without RSS feeds, you can:

### Use the existing scraper.py:
```bash
# Scrape articles from sites without RSS and generate custom feeds
PROSPECTS_CSV=prospects_no_rss.csv python3 scraper.py
```

The scraper will:
1. Visit each website
2. Extract article data using Firecrawl API
3. Generate custom RSS feeds

### Advantages:
- Works for **any site** even without RSS
- Creates standardized feed format
- You control update frequency

### Disadvantages:
- Uses Firecrawl API credits
- Slower than native RSS feeds
- Need to scrape regularly to keep feeds fresh

### Expected results:
- **All 1,047 prospects can have feeds** (100% coverage)
- API cost: ~$0.01 per prospect per scrape
- Monthly cost for 400 prospects: ~$40-50

---

## Strategy 3: Alternative Feed Sources

For prospects that are difficult:

### Social Media Feeds:
- Twitter/X RSS feeds via Nitter
- Facebook Page RSS (if available)
- LinkedIn company feeds

### News Aggregators:
- Google News RSS for company mentions
- Bing News RSS

### Implementation:
Would require additional scripts to:
1. Find social media profiles
2. Generate aggregator feed URLs
3. Filter for relevant content

---

## Recommended Approach

### Phase 1: Run Enhanced Discovery (Now)
```bash
python3 rss_discovery_enhanced.py
python3 update_prospects_with_discovered_feeds.py
```
**Expected gain: +100-150 feeds**

### Phase 2: Selective Synthetic Feeds (After Phase 1)
For high-value prospects without RSS:
1. Create filtered list of top prospects
2. Run scraper.py on that subset
3. Monitor API costs

**Expected gain: +50-100 feeds**

### Phase 3: Re-run Discovery Periodically (Quarterly)
Sites add RSS feeds over time:
- New sites might add feeds
- Sites redesign and add RSS
- New content management systems

**Expected gain: +10-20 feeds per quarter**

---

## Quick Start

To immediately improve your feed count:

```bash
# 1. Run enhanced discovery
python3 rss_discovery_enhanced.py

# This will take ~10-15 minutes for 560 prospects
# It checks each prospect using 3 different methods

# 2. Update prospects.csv
python3 update_prospects_with_discovered_feeds.py

# 3. Commit and push
git add prospects.csv
git commit -m "Add newly discovered RSS feeds from enhanced discovery"
git push

# 4. The workflow will automatically start using these new feeds
```

---

## Monitoring Success

After running enhanced discovery, check:

```bash
# Count feeds
grep -v "^id," prospects.csv | grep -c ","

# Count prospects with feeds
awk -F',' 'NR>1 && $4 != "" {count++} END {print count}' prospects.csv
```

---

## Next Steps

1. **Run Phase 1 now** to get quick wins
2. **Evaluate results** - did we reach 60%+?
3. **If still under 70%**: Consider Phase 2 for high-value prospects
4. **Set up quarterly re-discovery** to catch new feeds

---

## Cost Analysis

| Strategy | Additional Feeds | Time | API Cost |
|----------|-----------------|------|----------|
| Enhanced Discovery | +100-150 | 15 min | $0 |
| Synthetic Feeds (all) | +400 | 2-3 hours | ~$400 |
| Synthetic Feeds (selective) | +50-100 | 30 min | ~$50 |

**Recommendation**: Start with Enhanced Discovery (free, fast) then evaluate if synthetic feeds are worth the cost for specific high-value prospects.
