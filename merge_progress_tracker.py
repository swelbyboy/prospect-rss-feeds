#!/usr/bin/env python3
"""
Merge prospects.csv and new prospects into the progress tracker.
"""

import csv

# File paths
PROGRESS_TRACKER = "Newsletter outreach #2 - Progress tracker.csv"
PROSPECTS = "prospects.csv"
NEW_PROSPECTS = "20251126_Prospects with and without Newsletters - Prospect Domains - WITH Newsletter.csv"
OUTPUT_FILE = "Newsletter outreach #2 - Progress tracker - UPDATED.csv"

def extract_domain(url):
    """Extract clean domain from URL."""
    if not url or not url.strip():
        return ''
    domain = url.replace('http://', '').replace('https://', '').replace('www.', '')
    domain = domain.split('/')[0].strip()
    return domain.lower()

def main():
    print("🔄 Merging progress tracker with prospects and new domains...")

    # Load existing progress tracker
    progress_rows = []
    with open(PROGRESS_TRACKER, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        progress_rows = list(reader)
    print(f"📋 Loaded {len(progress_rows)} existing prospects from progress tracker")

    # Get existing domains (case-insensitive)
    existing_domains = set(row['Domain'].lower() for row in progress_rows)

    # Load prospects.csv (with discovered feeds)
    prospects_rows = []
    with open(PROSPECTS, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        prospects_rows = list(reader)
    print(f"📥 Loaded {len(prospects_rows)} prospects from prospects.csv")

    # Create domain->prospect mapping for prospects.csv
    prospects_by_domain = {}
    for prospect in prospects_rows:
        prospects_by_domain[prospect['domain'].lower()] = prospect

    # Track new additions
    new_rows = []
    added_with_feed = 0
    added_no_feed = 0

    # Process prospects.csv
    for prospect in prospects_rows:
        domain = prospect['domain'].lower()

        # Skip if already in progress tracker
        if domain in existing_domains:
            continue

        # Check if has RSS feed
        rss_feed = prospect.get('rss_feed', '').strip()

        if rss_feed:
            # Has feed - add with "To Do" status
            new_row = {
                'Prospect Name': prospect['company_name'],
                'RSS Feed': rss_feed,
                'Data Source': 'RSS',  # Discovered RSS feed
                'Last Scrape Status': 'pending',
                'Last Scrape Timestamp': '',
                'Country': prospect.get('country', ''),
                'Domain': prospect['domain'],
                'Status': 'To Do',
                'Existing newsletter?': 'FALSE',
                'Person': '',
                'Date sent': '',
                'Replied': 'FALSE',
                'Comments': 'Newly discovered RSS feed'
            }
            added_with_feed += 1
        else:
            # No feed - add with "No feed generated" status
            new_row = {
                'Prospect Name': prospect['company_name'],
                'RSS Feed': '-',
                'Data Source': 'N/A',
                'Last Scrape Status': 'pending',
                'Last Scrape Timestamp': '',
                'Country': prospect.get('country', ''),
                'Domain': prospect['domain'],
                'Status': 'No feed generated',
                'Existing newsletter?': 'FALSE',
                'Person': '',
                'Date sent': '',
                'Replied': 'FALSE',
                'Comments': ''
            }
            added_no_feed += 1

        new_rows.append(new_row)
        existing_domains.add(domain)  # Track as added

    print(f"  ✅ From prospects.csv - added {added_with_feed} with feeds, {added_no_feed} without")

    # Load new prospects (WITH newsletter)
    new_prospects_rows = []
    with open(NEW_PROSPECTS, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        new_prospects_rows = list(reader)
    print(f"📥 Loaded {len(new_prospects_rows)} new prospects (WITH newsletter)")

    added_new_with_feed = 0
    added_new_no_feed = 0
    skipped = 0

    for prospect in new_prospects_rows:
        # Extract domain from Website URL
        domain = extract_domain(prospect.get('Website URL', ''))

        if not domain:
            continue

        # Skip if already in progress tracker or already added
        if domain in existing_domains:
            skipped += 1
            continue

        # Check if this domain has a feed in prospects.csv
        matching_prospect = prospects_by_domain.get(domain)

        if matching_prospect:
            rss_feed = matching_prospect.get('rss_feed', '').strip()
        else:
            rss_feed = ''

        if rss_feed:
            # Has feed - add with "To Do" status
            new_row = {
                'Prospect Name': prospect['Company name'],
                'RSS Feed': rss_feed,
                'Data Source': 'RSS',
                'Last Scrape Status': 'pending',
                'Last Scrape Timestamp': '',
                'Country': prospect.get('Country', ''),
                'Domain': domain,
                'Status': 'To Do',
                'Existing newsletter?': 'TRUE',
                'Person': '',
                'Date sent': '',
                'Replied': 'FALSE',
                'Comments': 'Has existing newsletter - RSS feed found'
            }
            added_new_with_feed += 1
        else:
            # No feed - leave status blank (haven't searched yet)
            new_row = {
                'Prospect Name': prospect['Company name'],
                'RSS Feed': '-',
                'Data Source': 'N/A',
                'Last Scrape Status': 'pending',
                'Last Scrape Timestamp': '',
                'Country': prospect.get('Country', ''),
                'Domain': domain,
                'Status': '',  # Blank - not searched yet
                'Existing newsletter?': 'TRUE',
                'Person': '',
                'Date sent': '',
                'Replied': 'FALSE',
                'Comments': 'Has existing newsletter - not searched for RSS yet'
            }
            added_new_no_feed += 1

        new_rows.append(new_row)
        existing_domains.add(domain)

    print(f"  ✅ From new prospects - added {added_new_with_feed} with feeds, {added_new_no_feed} without")
    print(f"  ⏭️  Skipped {skipped} duplicates")

    # Combine all rows
    all_rows = progress_rows + new_rows

    # Save updated progress tracker
    fieldnames = ['Prospect Name', 'RSS Feed', 'Data Source', 'Last Scrape Status',
                  'Last Scrape Timestamp', 'Country', 'Domain', 'Status',
                  'Existing newsletter?', 'Person', 'Date sent', 'Replied', 'Comments']

    with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print("\n" + "="*80)
    print("📊 MERGE SUMMARY")
    print("="*80)
    print(f"Original progress tracker: {len(progress_rows)} rows")
    print(f"\nAdded from prospects.csv:")
    print(f"  ✅ With RSS feed (To Do): {added_with_feed}")
    print(f"  ❌ Without feed (No feed generated): {added_no_feed}")
    print(f"\nAdded from new prospects (WITH newsletter):")
    print(f"  ✅ With RSS feed (To Do): {added_new_with_feed}")
    print(f"  ❌ Without feed (No feed generated): {added_new_no_feed}")
    print(f"  ⏭️  Skipped (duplicates): {skipped}")
    print(f"\n📝 Final progress tracker: {len(all_rows)} rows")
    print(f"   (+{len(all_rows) - len(progress_rows)} new rows)")
    print("="*80)
    print(f"\n✅ Updated progress tracker saved to: {OUTPUT_FILE}")
    print(f"   Review it before replacing the original file")

if __name__ == '__main__':
    main()
