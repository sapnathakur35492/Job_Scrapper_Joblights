import os
import django
import cloudscraper
from bs4 import BeautifulSoup
import sys

sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})

url = "https://migratemate.co/jobs/amazon-senior-product-manager-340176"
print(f"Fetching {url}...")
resp = s.get(url, timeout=15)
print(f"Status: {resp.status_code}")

soup = BeautifulSoup(resp.text, 'html.parser')
links = []
for a in soup.find_all('a', href=True):
    href = a['href']
    if 'migratemate.co' not in href and href.startswith('http'):
        links.append((a.text.strip(), href))

print("\nExternal links:")
for text, l in links:
    print(f"  {text}: {l}")

scripts = soup.find_all('script', type='application/ld+json')
for s in scripts:
    print("\nJSON-LD found:")
    print(s.string[:500] + "...")
