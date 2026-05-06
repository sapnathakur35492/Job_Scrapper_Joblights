import os
import django
import sys
import logging

# Setup django environment
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.scrapers.sources import LinkResolver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('sociax_sync')
logger.setLevel(logging.INFO)

# Test job
job = {
    'title': 'Senior Software Engineer',
    'company': 'Amazon',
    'external_apply_link': 'https://migratemate.co/jobs/amazon-senior-software-engineer-123'
}

print(f"Resolving: {job['title']} at {job['company']}...")
resolved = LinkResolver.resolve_single(job, LinkResolver.session)
print(f"Resolved URL: {resolved}")
