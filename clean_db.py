import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.models import Job
from core.utils import is_valid_apply_url

print("Checking all jobs for invalid URLs...")
deleted = 0
for job in Job.objects.all():
    if not is_valid_apply_url(job.external_apply_link):
        print(f"Deleting invalid job: {job.title} at {job.company} -> {job.external_apply_link}")
        job.delete()
        deleted += 1

print(f"Deleted {deleted} invalid jobs.")
