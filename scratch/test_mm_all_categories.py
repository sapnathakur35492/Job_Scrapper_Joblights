import os
import django
import sys

# Setup django environment
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.scrapers.sources import MigrateMateScraper
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('sociax_sync')
logger.setLevel(logging.INFO)

scraper = MigrateMateScraper()

for slug, cat_name in scraper.CATEGORIES:
    print(f"\n--- Testing {cat_name} ({slug}) ---")
    # Manually override the random choice logic for testing
    scraper._test_slug = slug 
    
    # We need to monkeypatch fetch or just call _parse_html after fetching
    import cloudscraper
    s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
    url = f"https://migratemate.co/{slug}"
    try:
        resp = s.get(url, timeout=15)
        print(f"Status: {resp.status_code}")
        jobs = scraper._parse_html(resp.text, cat_name, slug)
        print(f"Found {len(jobs)} jobs!")
        for job in jobs[:2]:
            print(f"  {job['title']} | {job['company']}")
    except Exception as e:
        print(f"Error: {e}")
