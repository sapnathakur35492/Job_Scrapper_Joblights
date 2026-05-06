"""
Deep test: What exactly MigrateMate's ItemList contains
"""
import os, sys
sys.path.insert(0, '.')

import cloudscraper
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone as tz

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

test_url = "https://migratemate.co/h1b-jobs"
print(f"Fetching: {test_url}")
resp = scraper.get(test_url, timeout=30)
print(f"Status: {resp.status_code}, Size: {len(resp.text)}")

soup = BeautifulSoup(resp.text, 'html.parser')
scripts = soup.find_all('script', type='application/ld+json')

for s in scripts:
    try:
        data = json.loads(s.text)
        if isinstance(data, dict) and data.get('@type') == 'ItemList':
            print(f"\nFound ItemList with {len(data.get('itemListElement', []))} items")
            for element in data.get('itemListElement', []):
                item = element.get('item', {})
                if item.get('@type') == 'JobPosting':
                    title = item.get('title', '')
                    company = item.get('hiringOrganization', {}).get('name', '')
                    url = item.get('url', '')
                    date = item.get('datePosted', 'MISSING')
                    print(f"  Job: {title[:40]} | {company[:20]} | date={date} | url={url[:60]}")
    except Exception as e:
        print(f"Parse error: {e}")

print("\nDONE")
