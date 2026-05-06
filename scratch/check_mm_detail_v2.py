import os
import django
import cloudscraper
from bs4 import BeautifulSoup
import sys
import re

sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})

url = "https://migratemate.co/jobs/amazon-senior-product-manager-340176"
print(f"Fetching {url}...")
resp = s.get(url, timeout=15)
print(f"Status: {resp.status_code}")

# Check for __NEXT_DATA__
print("\nChecking for __NEXT_DATA__...")
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">([^<]+)</script>', resp.text)
if m:
    data = m.group(1)
    print(f"Found __NEXT_DATA__ ({len(data)} bytes)")
    # Search for common ATS domains in this JSON
    for domain in ['workday', 'lever.co', 'greenhouse.io', 'ashbyhq.com']:
        if domain in data:
            print(f"  FOUND {domain} in __NEXT_DATA__!")
            # Try to extract the full URL
            url_match = re.search(f'"(https?://[^"]*{domain}[^"]*)"', data)
            if url_match:
                print(f"  Extracted URL: {url_match.group(1)}")
else:
    print("No __NEXT_DATA__ found.")

# Check for all strings that look like URLs
print("\nChecking for any external URLs in the page...")
urls = re.findall(r'https?://[^\s"\'<>]+', resp.text)
for u in urls:
    if 'migratemate.co' not in u and any(x in u for x in ['workday', 'lever.co', 'greenhouse.io', 'ashbyhq.com']):
        print(f"  FOUND potential ATS link: {u}")
