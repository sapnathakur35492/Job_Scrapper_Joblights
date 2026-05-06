import os
import django
import sys
import logging

# Setup django environment
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.scrapers.engine import ScraperEngine
from core.scrapers.sources import MigrateMateScraper, SimplifyScraper, JobrightScraper

# Mock Simplify and Jobright to return empty list so we only test MigrateMate
class MockSimplify(SimplifyScraper):
    def fetch(self): return []

class MockJobright(JobrightScraper):
    def fetch(self): return []

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('sociax_sync')
logger.setLevel(logging.INFO)

engine = ScraperEngine()

# Monkeypatch scrapers to only run MigrateMate
import core.scrapers.engine
original_scrapers = [SimplifyScraper(), JobrightScraper(), MigrateMateScraper()]

def run_test_sync():
    print("Starting Test Sync (MigrateMate only)...")
    # We will manually call fetch and filter to see what happens
    mm = MigrateMateScraper()
    raw_jobs = mm.fetch()
    print(f"MigrateMate returned {len(raw_jobs)} raw listings.")
    
    valid_jobs = []
    for raw in raw_jobs:
        if engine._is_job_valid(raw):
            valid_jobs.append(raw)
    
    print(f"Found {len(valid_jobs)} valid jobs after filtering.")
    
    for job in valid_jobs[:5]:
        print(f"  Valid: {job['title']} | {job['company']} | {job['posted_date']}")

run_test_sync()
