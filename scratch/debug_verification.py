import os
import django
import sys
import requests
from bs4 import BeautifulSoup
import re

sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.utils import is_live_apply_url

url = "https://jobs.grainger.com/job/LAKE-FOREST-Data-Engineer-330138-IL-60045-5201/1388134500/"
company = "Grainger"
title = "Data Engineer - 330138"

print(f"Testing URL: {url}")
res = is_live_apply_url(url, expected_company=company, expected_title=title)
print(f"Final Result: {res}")
