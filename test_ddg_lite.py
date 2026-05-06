import os
import django
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

title = "Software Engineer (Level 1)"
company = "Northrop Grumman Australia"
search_query = f"{title} {company} careers apply"

url = f"https://lite.duckduckgo.com/lite/"

s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
resp = s.post(url, data={'q': search_query}, timeout=15)
print("Status:", resp.status_code)

soup = BeautifulSoup(resp.text, 'html.parser')
for a in soup.find_all('a', class_='result-url'):
    href = a.get('href', '')
    print(href)
