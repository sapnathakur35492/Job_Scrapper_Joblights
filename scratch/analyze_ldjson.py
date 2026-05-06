import json
import re

with open("scratch/h1b_jobs.html", "r", encoding="utf-8") as f:
    content = f.read()

matches = re.findall(r'<script type="application/ld\+json">(.*?)</script>', content, re.DOTALL)
for i, m in enumerate(matches):
    try:
        data = json.loads(m)
        if data.get('@type') == 'ItemList':
            print(f"Match {i} is ItemList")
            print(json.dumps(data, indent=2)[:1000])
    except:
        pass
