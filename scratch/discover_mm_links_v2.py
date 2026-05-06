import os
import django
import cloudscraper
from bs4 import BeautifulSoup
import time
import sys
from urllib.parse import urljoin

sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})

urls = ["https://migratemate.co/", "https://migratemate.co/jobs"]

for url in urls:
    print(f"\nFetching {url}...")
    resp = s.get(url, timeout=15)
    print(f"Status: {resp.status_code}")

    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(url, href)
            if 'migratemate.co' in full_url:
                links.append((a.text.strip(), full_url))
        
        print(f"Found {len(links)} internal links.")
        for text, l in sorted(set(links))[:20]:
            print(f"  {text}: {l}")

        # Search for categories in text
        cat_keywords = ['h-1b', 'h1b', 'opt', 'cpt', 'tn', 'green card', 'visa', 'software', 'engineer']
        for text, l in set(links):
            if any(k in text.lower() or k in l.lower() for k in cat_keywords):
                print(f"  [MATCH] {text}: {l}")
