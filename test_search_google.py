import os
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sociax_sync.settings')
django.setup()

from googlesearch import search

title = "Software Engineer (Level 1)"
company = "Northrop Grumman Australia"
search_query = f"{title} {company} careers apply"

try:
    for url in search(search_query, num_results=5, sleep_interval=2):
        print(url)
except Exception as e:
    print(f"Error: {e}")
