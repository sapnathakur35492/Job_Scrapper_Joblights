import os
import django
import urllib.parse
from bs4 import BeautifulSoup

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.scrapers.sources import create_stealth_scraper

title = "Civil Engineer"
company = "Garver"
search_query = f"{title} {company} careers apply"
search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(search_query)}"

s = create_stealth_scraper()
s_resp = s.get(search_url, timeout=15)
print("Status:", s_resp.status_code)

soup = BeautifulSoup(s_resp.text, 'html.parser')
for a in soup.find_all('a', class_='result__url'):
    found_url = a.get('href', '')
    if found_url.startswith('//duckduckgo.com/l/?uddg='):
        found_url = urllib.parse.unquote(found_url.split('uddg=')[1].split('&')[0])
    print(found_url)
