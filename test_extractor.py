import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.scrapers.jobright_extractor import JobrightURLExtractor
import json

ext = JobrightURLExtractor()

# Test the three jobs the user complained about
urls = [
    'https://jobright.ai/jobs/info/69d9b0c2b67cec4f9b0a4042',  # SpaceX
    'https://jobright.ai/jobs/info/69a11e2e5218a81676725612',  # Booz Allen Hamilton
    'https://jobright.ai/jobs/info/69f811ad81706a5bd216ca0a'   # General Dynamics
]

for u in urls:
    print(f"Testing {u}")
    res = ext.extract(u)
    print(json.dumps(res, indent=2))
    print("-" * 50)
