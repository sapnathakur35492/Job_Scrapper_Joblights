import os
import django
import cloudscraper
from bs4 import BeautifulSoup
import sys

sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})

url = "https://migratemate.co/h1b-jobs"
print(f"Fetching {url}...")
resp = s.get(url, timeout=15)
print(f"Status: {resp.status_code}")
if "Wrong turn" in resp.text:
    print("Found 'Wrong turn' in body")
else:
    print("'Wrong turn' NOT found in body")

with open("scratch/h1b_jobs.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
