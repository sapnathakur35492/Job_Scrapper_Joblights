import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse
import time

s = cloudscraper.create_scraper()
query = 'site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com "SpaceX" "Mechanical Integration Test Engineer Starshield"'
url = 'https://www.bing.com/search?q=' + urllib.parse.quote(query)

resp = s.get(url)
print('Status:', resp.status_code)
soup = BeautifulSoup(resp.text, 'html.parser')
for a in soup.find_all('a', href=True):
    href = a['href']
    if 'greenhouse.io' in href or 'lever.co' in href:
        print('FOUND:', href)
