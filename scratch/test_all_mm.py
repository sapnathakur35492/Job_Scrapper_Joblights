import os
import django
import cloudscraper
from bs4 import BeautifulSoup
import time
import random

import sys
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

CATEGORIES = [
    ('h1b-jobs', 'H-1B'),
    ('opt-jobs', 'OPT/CPT'),
    ('tn-jobs', 'TN'),
    ('green-card-jobs', 'Green Card'),
    ('visa-sponsorship-jobs/software-engineer', 'Software Engineer'),
    ('visa-sponsorship-jobs/mechanical-engineer', 'Mechanical Engineer'),
    ('visa-sponsorship-jobs/product-manager', 'Product Manager'),
    ('visa-sponsorship-jobs/marketing-manager', 'Marketing Manager'),
    ('visa-sponsorship-jobs/civil-engineer', 'Civil Engineer'),
    ('visa-sponsorship-jobs/data-analyst', 'Data Analyst'),
    ('visa-sponsorship-jobs/business-analyst', 'Business Analyst'),
    ('visa-sponsorship-jobs/finance-analyst', 'Finance Analyst'),
]

s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})

for slug, name in CATEGORIES:
    url = f"https://migratemate.co/{slug}"
    print(f"Testing {name} ({url})...")
    try:
        resp = s.get(url, timeout=15)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            if "Wrong turn" in resp.text:
                print("  Result: 404 (Wrong turn detected in body)")
            else:
                soup = BeautifulSoup(resp.text, 'html.parser')
                scripts = soup.find_all('script', type='application/ld+json')
                found_ld = False
                for script in scripts:
                    if script.string and '"@type":"ItemList"' in script.string:
                        found_ld = True
                        break
                if found_ld:
                    print("  Result: SUCCESS (JSON-LD found)")
                else:
                    print("  Result: WARNING (No JSON-LD Job ItemList found)")
        time.sleep(2)
    except Exception as e:
        print(f"  Error: {e}")
