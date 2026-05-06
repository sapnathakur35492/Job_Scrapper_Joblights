import os
import django
import urllib.parse
from bs4 import BeautifulSoup
import cloudscraper

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

title = "Software Engineer (Level 1)"
company = "Northrop Grumman Australia"
search_query = f"{title} {company} careers apply"
search_url = f"https://search.yahoo.com/search?p={urllib.parse.quote(search_query)}"

s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
s_resp = s.get(search_url, timeout=15)
print("Yahoo Status:", s_resp.status_code)

soup = BeautifulSoup(s_resp.text, 'html.parser')
for a in soup.find_all('a', href=True):
    href = a['href']
    if href.startswith('http') and 'yahoo.com' not in href:
        print(href)
