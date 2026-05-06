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

url = "https://migratemate.co/"
print(f"Fetching {url}...")
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
    
    print("\nFound links:")
    for text, l in set(links):
        if l != "https://migratemate.co/":
            print(f"  {text}: {l}")

    # Also look for any JSON-LD to see if there's any hint
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        print("\nJSON-LD found on home page:")
        print(script.string[:500] + "...")
