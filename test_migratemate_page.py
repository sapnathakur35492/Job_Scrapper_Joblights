import os
import django
import cloudscraper
from bs4 import BeautifulSoup

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

url = "https://migratemate.co/visa-sponsorship-jobs/mechanical-engineer"

s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
resp = s.get(url, timeout=15)
print("Status:", resp.status_code)

soup = BeautifulSoup(resp.text, 'html.parser')
links = []
for a in soup.find_all('a', href=True):
    href = a['href']
    if 'migratemate.co' not in href and href.startswith('http'):
        links.append(href)

print("External links on page:")
for l in set(links):
    print(l)
