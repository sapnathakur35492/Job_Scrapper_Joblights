"""Test multiple Jobright pages to find one with isCompanySiteLink=True"""
import cloudscraper
import json
from bs4 import BeautifulSoup
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'sociax_sync.settings'
django.setup()
from core.models import Job

s = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})

# Get 10 random jobright URLs from the database
jr_jobs = Job.objects.filter(
    source__icontains='jobright', 
    external_apply_link__icontains='jobright.ai'
).order_by('-id')[:10]

for job in jr_jobs:
    url = job.external_apply_link
    try:
        resp = s.get(url, timeout=8)
        if resp.status_code != 200:
            print(f"SKIP {job.company}: HTTP {resp.status_code}")
            continue
        soup = BeautifulSoup(resp.text, 'html.parser')
        helper_tag = soup.find('script', id='jobright-helper-job-detail-info')
        if helper_tag:
            hdata = json.loads(helper_tag.string or '{}')
            job_result = hdata.get('jobResult', {})
            company_result = hdata.get('companyResult', {})
            is_company = job_result.get('isCompanySiteLink', False)
            print(f"Company={job.company[:25]:25s} | isCompanySiteLink={is_company} | companyURL={company_result.get('companyURL', 'N/A')[:40]}")
        else:
            print(f"Company={job.company[:25]:25s} | NO HELPER JSON")
    except Exception as e:
        print(f"Company={job.company[:25]:25s} | ERROR: {e}")
