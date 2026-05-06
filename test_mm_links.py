"""
Find actual job card link patterns in MigrateMate HTML
"""
import sys
sys.path.insert(0, '.')

import cloudscraper
from bs4 import BeautifulSoup
import re

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

resp = scraper.get("https://migratemate.co/h1b-jobs", timeout=30)
print(f"Status: {resp.status_code}, Size: {len(resp.text)}")

soup = BeautifulSoup(resp.text, 'html.parser')

# Find ALL unique hrefs
all_hrefs = set()
for a in soup.find_all('a', href=True):
    href = a['href']
    if href and href != '#' and not href.startswith('http'):
        all_hrefs.add(href)

print(f"\nAll unique internal hrefs ({len(all_hrefs)}):")
for h in sorted(all_hrefs)[:40]:
    print(f"  {h}")

# Specifically look for job-like patterns
print("\nJob-like hrefs:")
for a in soup.find_all('a', href=True):
    href = a['href']
    if re.search(r'/(job|jobs|position|posting|careers)/', href or '', re.I):
        print(f"  {href} | text: {a.get_text(strip=True)[:30]}")
