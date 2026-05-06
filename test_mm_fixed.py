"""
Test MigrateMate with the NEW fixed parser
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
sys.path.insert(0, '.')
django.setup()

import importlib
import core.scrapers.sources as src_module
importlib.reload(src_module)

from core.scrapers.sources import MigrateMateScraper

print("=== Testing FIXED MigrateMate Scraper ===\n")
mm = MigrateMateScraper()
jobs = mm.fetch()
print(f"\nTotal jobs fetched: {len(jobs)}")
for j in jobs[:10]:
    print(f"  [{j.get('visa_type','?')}] {j.get('title','')[:40]} @ {j.get('company','')[:20]}")
    print(f"    URL: {j.get('external_apply_link','')[:80]}")
    print(f"    Date: {j.get('posted_date','')}")
