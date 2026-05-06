import os
import django
import sys
import logging

sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.scrapers.engine import ScraperEngine
from core.scrapers.sources import MigrateMateScraper

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('sociax_sync')

# Create engine
engine = ScraperEngine()
scraper = MigrateMateScraper()

print("Fetching from MigrateMate...")
jobs = scraper.fetch()
print(f"Found {len(jobs)} jobs from MigrateMate.")

valid_count = 0
for job in jobs:
    if engine._is_job_valid(job):
        print(f"  ✅ Valid: {job['title']} @ {job['company']}")
        resolved = engine._resolve_job_link(job)
        if resolved and engine._save_job(resolved):
            valid_count += 1
            print(f"    🚀 SAVED!")
    else:
        print(f"  ❌ Invalid: {job['title']} @ {job['company']}")

print(f"\nTotal Saved: {valid_count}")
