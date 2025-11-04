#!/usr/bin/env python3
"""
Convert input prospect data to the format needed by the scraper.
"""

import csv
from urllib.parse import urlparse

input_file = 'input_prospects.csv'
output_file = 'prospects.csv'

def clean_domain(url):
    """Extract clean domain from URL."""
    if not url:
        return ''

    # Parse the URL
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path

    # Remove www. prefix if present
    if domain.startswith('www.'):
        domain = domain[4:]

    # Remove trailing slashes
    domain = domain.rstrip('/')

    return domain

# Read input file and convert
prospects = []
with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for idx, row in enumerate(reader, 1):
        company_name = row.get('Company name', '').strip()
        website_url = row.get('Website URL', '').strip()

        if company_name and website_url:
            domain = clean_domain(website_url)
            if domain:
                prospects.append({
                    'id': idx,
                    'company_name': company_name,
                    'domain': domain
                })

# Write output file
with open(output_file, 'w', encoding='utf-8', newline='') as f:
    fieldnames = ['id', 'company_name', 'domain']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(prospects)

print(f"✅ Converted {len(prospects)} prospects")
print(f"📄 Output written to: {output_file}")
print("\nFirst 5 prospects:")
for p in prospects[:5]:
    print(f"  {p['id']}. {p['company_name']} - {p['domain']}")
