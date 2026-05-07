import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.models import Job
from core.utils import extract_job_metadata, is_experience_allowed

def clean_jobs():
    jobs = Job.objects.all()
    total = jobs.count()
    deleted = 0
    passed = 0
    
    print(f"Scanning {total} jobs for experience compliance (0-5 years)...")
    
    for j in jobs:
        meta = extract_job_metadata(j.title, j.description)
        # Ensure title is included in the metadata for keyword checking
        full_meta = meta | {'title': j.title}
        
        if not is_experience_allowed(full_meta, max_limit=5):
            print(f"  Deleting: {j.title[:40]} @ {j.company[:20]} ({j.experience_years})")
            j.delete()
            deleted += 1
        else:
            passed += 1
            
    print(f"\nCleanup Complete:")
    print(f"  Total scanned: {total}")
    print(f"  Deleted:       {deleted}")
    print(f"  Passed:        {passed}")

if __name__ == "__main__":
    clean_jobs()
