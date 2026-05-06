import os
import django
import sys

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.scrapers.sources import MigrateMateScraper
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('sociax_sync')
logger.setLevel(logging.INFO)

scraper = MigrateMateScraper()
print("Fetching from MigrateMate...")
jobs = scraper.fetch()
print(f"Found {len(jobs)} jobs!")
for job in jobs[:3]:
    print(job['title'], "|", job['company'], "|", job['posted_date'], "|", job['external_apply_link'])
