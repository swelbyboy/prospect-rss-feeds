#!/usr/bin/env python3
"""
Create a test prospects file with random selection.
"""

import csv
import random

input_file = 'prospects.csv'
output_file = 'prospects_test.csv'
num_to_select = 20

# Read all prospects
prospects = []
with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    prospects = list(reader)

# Randomly select prospects
selected = random.sample(prospects, min(num_to_select, len(prospects)))

# Write test file
with open(output_file, 'w', encoding='utf-8', newline='') as f:
    fieldnames = ['id', 'company_name', 'domain']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(selected)

print(f"✅ Created test file with {len(selected)} random prospects")
print(f"📄 Output written to: {output_file}")
print("\nSelected prospects:")
for idx, p in enumerate(selected, 1):
    print(f"  {idx}. {p['company_name']} - {p['domain']}")
