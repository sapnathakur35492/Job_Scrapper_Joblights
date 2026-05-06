import os
import django
import sys

sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.scrapers.sources import LinkResolver

job = {
    'title': 'Senior Product Manager',
    'company': 'NVIDIA',
    'external_apply_link': 'https://migratemate.co/jobs/nvidia-senior-product-manager-340243'
}

print(f"Resolving: {job['title']} @ {job['company']}")
resolved = LinkResolver.resolve_single(job, LinkResolver.session)
print(f"Resolved: {resolved}")
