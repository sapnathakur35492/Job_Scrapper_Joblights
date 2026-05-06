import os
import django

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from core.utils import is_valid_apply_url, is_live_apply_url

url = "https://migratemate.co/visa-sponsorship-jobs/civil-engineer"
title = "Civil Engineer I"
company = "CRAWFORD, MURPHY & TILLY"

valid = is_valid_apply_url(url)
print(f"is_valid_apply_url('{url}') -> {valid}")

live = is_live_apply_url(url, expected_company=company, expected_title=title)
print(f"is_live_apply_url('{url}') -> {live}")
