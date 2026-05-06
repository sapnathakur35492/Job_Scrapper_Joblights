import json
import re

with open('migratemate_dump.html', 'r', encoding='utf-8') as f:
    text = f.read()

urls = re.findall(r'https?://[^\s\"\'\\]+', text)
for u in urls:
    if 'greenhouse' in u or 'lever' in u or 'workday' in u or 'icims' in u or 'jobs' in u or 'careers' in u:
        print(u)
