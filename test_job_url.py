import requests

headers = {'User-Agent': 'Mozilla/5.0'}
for path in ['jobs', 'job']:
    url = f"https://migratemate.co/{path}/7ce318053f1ef864e67c70a28cd79f35"
    r = requests.get(url, headers=headers, allow_redirects=False)
    print(f"{url} -> {r.status_code}")
    if r.status_code in [301, 302, 307, 308]:
        print("Redirects to:", r.headers.get('Location'))
