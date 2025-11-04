#!/usr/bin/env python3
"""
Simple test to see raw Firecrawl response.
"""

from firecrawl import FirecrawlApp
from config import Config
import json

firecrawl = FirecrawlApp(api_key=Config.FIRECRAWL_API_KEY)

test_url = "https://thenerdstash.com"

print(f"Testing: {test_url}\n")

# Test with just markdown format first
result = firecrawl.scrape_url(test_url, params={'formats': ['markdown']})

print("Response keys:", list(result.keys()) if result else "None")
print()

if result:
    # Print metadata
    if 'metadata' in result:
        print("Metadata keys:", list(result['metadata'].keys()))
        print("Title:", result['metadata'].get('title', 'N/A'))
        print()

    # Check for markdown content
    if 'markdown' in result:
        markdown = result['markdown']
        print(f"Markdown length: {len(markdown)} characters")
        print("First 500 chars:")
        print(markdown[:500])
        print()

    # Look for any link-related keys
    print("\nAll top-level keys:")
    for key in result.keys():
        val = result[key]
        val_type = type(val).__name__
        if isinstance(val, (list, dict, str)):
            val_len = len(val)
            print(f"  {key}: {val_type}, length={val_len}")
        else:
            print(f"  {key}: {val_type}")
