#!/usr/bin/env python3
"""
Add new prospects from WITH Newsletter CSV to prospects.csv for RSS discovery.
"""

import csv

NEW_PROSPECTS = "20251126_Prospects with and without Newsletters - Prospect Domains - WITH Newsletter.csv"
PROSPECTS = "prospects.csv"
OUTPUT = "prospects.csv"

def extract_domain(url):
    """Extract clean domain from URL."""
    if not url or not url.strip():
        return ''
    domain = url.replace('http://', '').replace('https://', '').replace('www.', '')
    domain = domain.split('/')[0].strip()
    return domain

def main():
    print("📥 Adding new prospects to prospects.csv...")

    # Load existing prospects
    existing_prospects = []
    with open(PROSPECTS, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        existing_prospects = list(reader)

    print(f"📋 Loaded {len(existing_prospects)} existing prospects")

    # Get existing domains
    existing_domains = set(p['domain'].lower() for p in existing_prospects)

    # Load new prospects
    new_prospects_data = []
    with open(NEW_PROSPECTS, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        new_prospects_data = list(reader)

    print(f"📥 Loaded {len(new_prospects_data)} new prospects")

    # Find next ID
    max_id = max(int(p['id']) for p in existing_prospects if p['id'].isdigit())
    next_id = max_id + 1

    # Process new prospects
    new_rows = []
    added = 0
    skipped = 0

    for prospect in new_prospects_data:
        domain = extract_domain(prospect.get('Website URL', ''))

        if not domain:
            continue

        # Skip if already exists
        if domain.lower() in existing_domains:
            skipped += 1
            continue

        # Add new prospect
        new_row = {
            'id': str(next_id),
            'company_name': prospect['Company name'],
            'domain': domain,
            'rss_feed': '',  # Empty - will be filled by discovery
            'email': '',
            'contact_name': '',
            'notes': 'Has existing newsletter',
            'country': prospect.get('Country', '')
        }
        new_rows.append(new_row)
        existing_domains.add(domain.lower())
        next_id += 1
        added += 1

    # Combine and save
    all_prospects = existing_prospects + new_rows

    fieldnames = ['id', 'company_name', 'domain', 'rss_feed', 'email', 'contact_name', 'notes', 'country']

    with open(OUTPUT, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_prospects)

    print("\n" + "="*80)
    print(f"✅ Added {added} new prospects to prospects.csv")
    print(f"⏭️  Skipped {skipped} duplicates")
    print(f"📝 Total prospects: {len(all_prospects)} (was {len(existing_prospects)})")
    print("="*80)
    print(f"\n✅ Updated prospects.csv")
    print(f"\n💡 Next: Run RSS discovery to find feeds for new prospects:")
    print(f"   python3 rss_discovery.py")

if __name__ == '__main__':
    main()
