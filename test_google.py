from googlesearch import search
query = 'site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com "SpaceX" "Mechanical Integration Test Engineer Starshield"'
print('Query:', query)
for url in search(query, num_results=5, sleep_interval=1):
    print(url)
