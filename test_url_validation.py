import re

def test_url(url):
    path = url.lower()
    has_id = bool(re.search(r'[0-9]{4,}|[a-f0-9]{8,}-[a-f0-9]{4}-', path))
    print(f"{url} -> has_id: {has_id}")

test_url("https://www.northropgrumman.com/careers/careers-in-australia")
test_url("https://ochsner.wd1.myworkdayjobs.com/ochsner/job/New-Orleans/AI-Agent-Engineer_REQ-12345")
test_url("https://boards.greenhouse.io/spacex/jobs/5764870004")
test_url("https://careers.google.com/jobs/results/143521361234")
test_url("https://www.tesla.com/careers/search/job/software-engineer-12345")
test_url("https://www.company.com/careers/software-engineer")
