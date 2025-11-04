#!/usr/bin/env python3
"""
Debug script to see what Firecrawl returns.
"""

from firecrawl import FirecrawlApp
from config import Config
import json

firecrawl = FirecrawlApp(api_key=Config.FIRECRAWL_API_KEY)

test_url = "https://thenerdstash.com"

print(f"Testing Firecrawl scrape on: {test_url}\n")

# Test scrape
result = firecrawl.scrape_url(test_url, params={'formats': ['markdown', 'links']})

print("=" * 60)
print("RESULT KEYS:")
print("=" * 60)
if result:
    print(json.dumps(list(result.keys()), indent=2))

    print("\n" + "=" * 60)
    print("METADATA:")
    print("=" * 60)
    if 'metadata' in result:
        print(json.dumps(result['metadata'], indent=2)[:500])

    print("\n" + "=" * 60)
    print("LINKS (first 20):")
    print("=" * 60)
    if 'links' in result:
        print(f"Total links: {len(result.get('links', []))}")
        print(json.dumps(result['links'][:20], indent=2))
    else:
        print("No 'links' key found!")
        print("\nAll keys:", list(result.keys()))

    # Check for alternative keys
    print("\n" + "=" * 60)
    print("CHECKING FOR OTHER LINK KEYS:")
    print("=" * 60)
    for key in result.keys():
        if 'link' in key.lower() or 'url' in key.lower():
            print(f"Found key: {key}")
            val = result[key]
            if isinstance(val, list):
                print(f"  Type: list, Length: {len(val)}")
                print(f"  First few items: {val[:3]}")
            else:
                print(f"  Type: {type(val)}, Value preview: {str(val)[:100]}")
else:
    print("No result returned!")
