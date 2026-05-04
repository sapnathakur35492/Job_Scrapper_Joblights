import cloudscraper
import re
import json

s = cloudscraper.create_scraper()
r = s.get('https://jobright.ai/jobs/info/69d9b0c2b67cec4f9b0a4042')
urls = re.findall(r'https?://[^\s"\'<>]+', r.text.lower())
print("Found URLs:")
for u in set(urls):
    if 'jobright' not in u and 'w3.org' not in u and 'google' not in u:
        print(u)
