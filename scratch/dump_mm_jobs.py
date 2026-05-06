import os
import django
import cloudscraper
from bs4 import BeautifulSoup
import sys

sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})

url = "https://migratemate.co/jobs"
print(f"Fetching {url}...")
resp = s.get(url, timeout=15)
print(f"Status: {resp.status_code}")

with open("scratch/mm_jobs.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
