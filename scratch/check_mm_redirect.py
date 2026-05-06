import os
import django
import cloudscraper
from bs4 import BeautifulSoup
import sys

sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})

urls = ["https://migratemate.co/h1b-jobs", "https://migratemate.co/opt-jobs"]

for url in urls:
    print(f"Fetching {url}...")
    resp = s.get(url, timeout=15, allow_redirects=True)
    print(f"  Final URL: {resp.url}")
    print(f"  Status: {resp.status_code}")
    print(f"  Title: {BeautifulSoup(resp.text, 'html.parser').title.string if BeautifulSoup(resp.text, 'html.parser').title else 'No Title'}")
