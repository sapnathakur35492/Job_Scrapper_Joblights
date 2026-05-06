import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

import logging
logging.getLogger('sociax_sync').setLevel(logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler())

from core.utils import is_live_apply_url
from django.core.cache import cache
cache.clear()

url = "https://cambiumlearning.wd1.myworkdayjobs.com/camb/job/Remote/Assessment-Technical-Data-Analyst-Intern_REQ-4429"
title = "Assessment Technical Data Analyst Intern"
company = "Cambium Assessment"

result = is_live_apply_url(url, expected_company=company, expected_title=title)
print("Result of is_live_apply_url:", result)
