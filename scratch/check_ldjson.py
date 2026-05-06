import sys

with open("scratch/h1b_jobs.html", "r", encoding="utf-8") as f:
    content = f.read()

if "application/ld+json" in content:
    print("Found application/ld+json")
    # Find and print snippets
    import re
    matches = re.findall(r'<script type="application/ld\+json">(.*?)</script>', content, re.DOTALL)
    for i, m in enumerate(matches):
        print(f"Match {i}: {m[:200]}...")
else:
    print("NOT found application/ld+json")
