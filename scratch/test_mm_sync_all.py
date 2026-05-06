import os
import django
import sys
import logging
from datetime import datetime, timezone as tz

# Setup django environment
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.scrapers.engine import ScraperEngine
from core.scrapers.sources import MigrateMateScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('sociax_sync')
logger.setLevel(logging.INFO)

engine = ScraperEngine()

def run_test_sync():
    print("Starting Test Sync (MigrateMate ALL CATEGORIES)...")
    mm = MigrateMateScraper()
    
    total_valid = 0
    for slug, cat_name in mm.CATEGORIES:
        print(f"\n--- Testing Category: {cat_name} ({slug}) ---")
        try:
            import cloudscraper
            s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
            url = f"https://migratemate.co/{slug}"
            resp = s.get(url, timeout=15)
            raw_jobs = mm._parse_html(resp.text, cat_name, slug)
            print(f"MigrateMate returned {len(raw_jobs)} raw listings.")
            
            cat_valid = 0
            for raw in raw_jobs:
                if engine._is_job_valid(raw):
                    print(f"  Valid: {raw['title']} | {raw['company']} | {raw['posted_date']}")
                    cat_valid += 1
                    total_valid += 1
                else:
                    # Let engine._is_job_valid log the failure
                    pass
            print(f"Category {cat_name}: {cat_valid} valid jobs.")
        except Exception as e:
            print(f"Error in {cat_name}: {e}")
            
    print(f"\nTotal valid jobs across all categories: {total_valid}")

run_test_sync()
