import os
import django
import sys
from django.utils import timezone

sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.models import Job
from core.utils import is_live_apply_url

print("Checking 5 most recent jobs...")
jobs = Job.objects.order_by('-created_at')[:5]

if not jobs:
    print("No jobs found in database.")
    sys.exit(0)

for j in jobs:
    print(f"\n--- {j.title} at {j.company} ---")
    print(f"Source: {j.source}")
    print(f"Apply URL: {j.external_apply_link}")
    
    # Run the live verification
    is_live = is_live_apply_url(j.external_apply_link, expected_company=j.company, expected_title=j.title)
    print(f"VERIFICATION RESULT: {'✅ LIVE & CORRECT' if is_live else '❌ DEAD OR MISMATCHED'}")
