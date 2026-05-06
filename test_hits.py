import re

with open('migratemate_dump.html', 'r', encoding='utf-8') as f:
    text = f.read()

scripts = re.findall(r'<script[^>]*>(.*?)</script>', text, re.DOTALL)
for s in scripts:
    if 'total_visas' in s:
        print("Script length:", len(s))
        print("First 2000 chars:")
        print(s[:2000])
