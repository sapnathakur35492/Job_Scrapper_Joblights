import cloudscraper
import json
from bs4 import BeautifulSoup
import re

s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
resp = s.get('https://migratemate.co/h1b-jobs/project-manager')
html = resp.text
print(resp.status_code)

if resp.status_code != 200:
    print(html[:200])

soup = BeautifulSoup(html, 'html.parser')
scripts = soup.find_all('script')
print(f"Total scripts: {len(scripts)}")
for s in scripts:
    if '__NEXT_DATA__' in s.get_text():
        print("FOUND NEXT DATA in text!")

nd = soup.find('script', id='__NEXT_DATA__')
if nd:
    data = json.loads(nd.string)
    print("Keys:", list(data.keys()))
    if 'props' in data:
        print("pageProps keys:", data['props']['pageProps'].keys())
        # Let's just find ANY string starting with http and having greenhouse/workday etc.
        def find_urls(obj):
            urls = []
            if isinstance(obj, str):
                if obj.startswith('http') and any(x in obj for x in ['greenhouse', 'workday', 'lever', 'icims', 'jobvite', 'wd1']):
                    urls.append(obj)
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if k == 'url' and isinstance(v, str) and v.startswith('http'): urls.append(v)
                    urls.extend(find_urls(v))
            elif isinstance(obj, list):
                for v in obj:
                    urls.extend(find_urls(v))
            return urls
        
        found = find_urls(data)
        print(f"Found ATS URLs: {len(found)}")
        for f in found[:5]:
            print(f)
