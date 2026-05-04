import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse
s = cloudscraper.create_scraper()
query = 'site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com "SpaceX" "Mechanical Integration Test Engineer Starshield"'
url = 'https://search.yahoo.com/search?p=' + urllib.parse.quote(query)
resp = s.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
soup = BeautifulSoup(resp.text, 'html.parser')
for a in soup.find_all('a', href=True):
    href = a['href']
    if 'greenhouse.io' in href or 'lever.co' in href:
        print(href)
