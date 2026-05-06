import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
sys.path.insert(0, '.')
django.setup()

from core.models import Job
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count

now = timezone.now()
total = Job.objects.count()
h24 = Job.objects.filter(posted_date__gte=now - timedelta(hours=24)).count()
h48 = Job.objects.filter(posted_date__gte=now - timedelta(hours=48)).count()

print(f"=== DB Status ===")
print(f"Total jobs in DB : {total}")
print(f"Jobs within 24h  : {h24}")
print(f"Jobs within 48h  : {h48}")
print(f"\n--- Source Breakdown ---")
for s in Job.objects.values('source').annotate(c=Count('id')).order_by('-c'):
    print(f"  {s['source']}: {s['c']}")

print(f"\n--- Recent 5 jobs ---")
for j in Job.objects.order_by('-created_at')[:5]:
    print(f"  [{j.source}] {j.title[:40]} @ {j.company[:20]} | {j.posted_date}")
