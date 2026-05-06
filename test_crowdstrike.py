import cloudscraper
import urllib.parse
from bs4 import BeautifulSoup

s = cloudscraper.create_scraper()
query = 'site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com "CrowdStrike" "Intern"'
url = 'https://search.yahoo.com/search?p=' + urllib.parse.quote(query)
resp = s.get(url, headers={'User-Agent': 'Mozilla/5.0'})
soup = BeautifulSoup(resp.text, 'html.parser')
for a in soup.find_all('a', href=True):
    href = a['href']
    if 'RU=' in href:
        try:
            print(urllib.parse.unquote(href.split('RU=')[1].split('/RK=')[0]))
        except: pass
