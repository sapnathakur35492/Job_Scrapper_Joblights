"""
Quick test: Why is MigrateMate returning 0 jobs?
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
sys.path.insert(0, '.')
django.setup()

import requests
import cloudscraper
from bs4 import BeautifulSoup
import json

print("=== Testing MigrateMate scraping ===\n")

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

test_url = "https://migratemate.co/h1b-jobs"
print(f"Fetching: {test_url}")
try:
    resp = scraper.get(test_url, timeout=20)
    print(f"Status: {resp.status_code}")
    print(f"Content-Length: {len(resp.text)}")
    
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, 'html.parser')
        scripts = soup.find_all('script', type='application/ld+json')
        print(f"JSON-LD scripts found: {len(scripts)}")
        
        for i, s in enumerate(scripts):
            content = s.text.strip()[:200]
            print(f"\nScript {i}: {content[:100]}...")
            try:
                data = json.loads(s.text)
                dtype = data.get('@type', 'unknown') if isinstance(data, dict) else 'list'
                print(f"  @type: {dtype}")
                if isinstance(data, dict) and data.get('@type') == 'ItemList':
                    items = data.get('itemListElement', [])
                    print(f"  itemListElement count: {len(items)}")
                    if items:
                        print(f"  First item: {str(items[0])[:200]}")
            except Exception as e:
                print(f"  JSON parse error: {e}")
        
        # Check for bot block signatures
        html_lower = resp.text[:1000].lower()
        if 'cloudflare' in html_lower:
            print("\n🛡️ CLOUDFLARE DETECTED!")
        elif 'datadome' in html_lower:
            print("\n🛡️ DATADOME DETECTED!")
        elif 'captcha' in html_lower:
            print("\n🛡️ CAPTCHA DETECTED!")
        else:
            print("\n✅ No obvious bot protection detected")
            print(f"HTML snippet: {resp.text[:300]}")
    else:
        print(f"❌ HTTP Error: {resp.status_code}")
        print(resp.text[:200])
except Exception as e:
    print(f"❌ Exception: {e}")

print("\n=== DONE ===")
