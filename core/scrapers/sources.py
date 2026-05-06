"""
Sociax Sync — 3 Source Scrapers
Only: Simplify Jobs, Jobright.ai, MigrateMate
"""
import re
import json
import logging
import requests
import time
import random
import cloudscraper
import hashlib
from datetime import datetime, timezone as tz
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger('sociax_sync')

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

# Setup advanced scraping session
def create_stealth_scraper():
    return cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

scraper = create_stealth_scraper()
scraper.headers.update({
    'Accept-Language': 'en-US,en;q=0.9',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'DNT': '1',
})

def get_with_retry(session, url, attempts=3, delay_range=(0.6, 1.4), **kwargs):
    """HTTP GET with retry and jittered delay."""
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            resp = session.get(url, **kwargs)
            if resp.status_code < 500:
                return resp
        except Exception as exc:
            last_exc = exc
        if attempt < attempts:
            time.sleep(random.uniform(*delay_range))
    if last_exc:
        raise last_exc
    return None


# ═══════════════════════════════════════════════════════════
#  LINK RESOLVER — Get Direct Company Links
# ═══════════════════════════════════════════════════════════
class LinkResolver:
    """
    Utility to resolve intermediate job portal links (Jobright, MigrateMate)
    to direct company career sites (Workday, Lever, Greenhouse, etc.).
    """
    COMMON_PORTALS = [
        'workday', 'lever.co', 'greenhouse.io', 'ashbyhq.com', 'breezy.hr',
        'smartrecruiters.com', 'myworkdayjobs.com', 'jobs.ashbyhq.com',
        'applytojob.com', 'jobvite.com', 'recruitee.com', 'personio.',
        'taleo.net', 'icims.com', 'brassring.com', 'avature.net', 'successfactors',
        'workable.com', 'rippling-ats.com', 'jobscore.com', 'freshteam.com'
    ]
    
    NEWS_SITES = [
        'news.', 'blog.', 'press.', 'article.', 'story.', 'crunchbase', 'alleywatch', 
        'siliconangle', 'businesswire', 'prnewswire', 'techcrunch', 'forbes', 
        'bloomberg', 'reuters', 'inc.com', 'fastcompany', 'medium.com', 'venturebeat', 
        'marketwatch', 'cnbc', 'wsj', 'nytimes', 'fortune', 'entrepreneur', 
        'businessinsider', 'theverge', 'wired', 'zdnet', 'gizmodo', 'engadget',
        'decrypt.co', 'disruptafrica', 'techrseries', 'bizjournals', 'sfchronicle',
        'denverpost', 'chicagotribune', 'latimes', 'bostonglobe'
    ]
    session = scraper # Map global scraper here

    @classmethod
    def resolve_batch(cls, jobs, scraper_session=None, max_workers=5):
        """Resolves links for a list of jobs in parallel."""
        log.info(f"    🔍 Resolving direct links for {len(jobs)} jobs...")
        
        # Use provided session or global scraper
        session = scraper_session or scraper
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_job = {}
            for job in jobs:
                link = job.get('external_apply_link', '')
                if any(x in link for x in ['jobright.ai', 'migratemate.co']):
                    future_to_job[executor.submit(cls.resolve_single, job, session)] = job
            
            for future in as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    direct_link = future.result()
                    if direct_link:
                        job['external_apply_link'] = direct_link
                        log.info(f"      🔗 Resolved: {job['company'][:15]} -> {urlparse(direct_link).netloc}")
                except Exception:
                    pass

    @classmethod
    def resolve_single(cls, job, session):
        """Resolves a single intermediate link."""
        url = job.get('external_apply_link', '') if isinstance(job, dict) else job
        try:
            # Handle Jobright links using the new extractor engine
            if 'jobright.ai/jobs/info/' in url:
                from core.scrapers.jobright_extractor import extract_jobright_url
                result = extract_jobright_url(url)
                if result and result.get('status') == 'success':
                    log.info(f"      ✨ Jobright extracted: {result.get('final_url')[:50]}...")
                    return result.get('final_url')
                return None
                
            # Handle MigrateMate links via DuckDuckGo/Yahoo Search
            if 'migratemate.co' in url and isinstance(job, dict):
                title = job.get('title', '')
                company = job.get('company', '')
                if title and company:
                    # Priority order: ATS-site-specific → general careers
                    search_queries = [
                        f'site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com "{company}" "{title}"',
                        f'"{title}" "{company}" site:greenhouse.io OR site:lever.co OR site:workday.com',
                        f'{title} {company} careers apply job',
                    ]
                    
                    for search_query in search_queries:
                        # Try DDG first
                        try:
                            try:
                                from ddgs import DDGS
                            except ImportError:
                                from duckduckgo_search import DDGS

                            with DDGS() as ddgs:
                                results = list(ddgs.text(search_query))
                                for res in results:
                                    res_url = res.get('href', '')
                                    if any(portal in res_url.lower() for portal in cls.COMMON_PORTALS):
                                        log.info(f"      🎯 DDG found ATS for {company}: {res_url[:60]}")
                                        return res_url
                        except Exception as e:
                            log.debug(f"      ⚠️ DDG failed: {e}")
                        
                        # Yahoo Search fallback
                        try:
                            import urllib.parse
                            yahoo_url = f"https://search.yahoo.com/search?p={urllib.parse.quote(search_query)}"
                            resp = get_with_retry(session, yahoo_url, timeout=12, attempts=3)
                            if not resp:
                                continue
                            if resp.status_code == 200:
                                soup = BeautifulSoup(resp.text, 'html.parser')
                                for a in soup.find_all('a', href=True):
                                    href = a['href']
                                    # Yahoo wraps: RU=https%3a%2f%2fboards.greenhouse.io.../RK=...
                                    if 'RU=' in href:
                                        try:
                                            ru = href.split('RU=')[1].split('/RK=')[0].split('/RS=')[0]
                                            href = urllib.parse.unquote(ru)
                                        except Exception:
                                            pass
                                    if href.startswith('http') and 'yahoo.com' not in href:
                                        if any(portal in href.lower() for portal in cls.COMMON_PORTALS):
                                            log.info(f"      🎯 Yahoo found ATS for {company}: {href[:60]}")
                                            return href
                        except Exception as e:
                            log.debug(f"      ⚠️ Yahoo fallback failed: {e}")
                
                return None  # All searches failed

            # Handle others
            # Random delay to be nice
            time.sleep(random.uniform(0.5, 1.5))
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://google.com/',
            }
            
            resp = get_with_retry(session, url, headers=headers, timeout=15, allow_redirects=True, attempts=3)
            if not resp:
                return None
            
            # Anti-Bot 401/403 Handling
            if resp.status_code in [401, 403]:
                log.info(f"      🛡️ 401/403 blocked on {urlparse(url).netloc}, retrying with new headers...")
                time.sleep(2)
                headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
                headers['Referer'] = 'https://linkedin.com/'
                resp = get_with_retry(session, url, headers=headers, timeout=15, allow_redirects=True, attempts=3)
                if not resp:
                    return None
                
                if resp.status_code in [401, 403]:
                    log.warning(f"      ❌ Still blocked (401/403), safely skipping: {urlparse(url).netloc}")
                    return None
            
            if resp.status_code != 200:
                return None
                
            # If the redirect brought us to a completely new URL, check if that URL is valid
            final_url = resp.url
            if final_url and final_url != url:
                # If it's a direct ATS link, we found the destination
                from core.utils import is_valid_apply_url
                if is_valid_apply_url(final_url):
                    return final_url
                # If the redirect led to a homepage or invalid URL, reject it
                if any(x in final_url for x in ['jobright.ai', 'migratemate.co', 'simplify.jobs', 'github.com']):
                    pass # Still an intermediary, need to parse HTML
                else:
                    return None # Redirected to an invalid non-ATS page

            # If we are here, we might need to parse HTML for a portal link
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Strategy 1: Look for common portals in the HTML
            for a in soup.find_all('a', href=True):
                href = a['href']
                if any(portal in href.lower() for portal in cls.COMMON_PORTALS):
                    return href
            
            # Strategy 2: Look for 'Apply' buttons/links that aren't internal
            for a in soup.find_all('a', href=True, string=re.compile(r'Apply', re.I)):
                href = a['href']
                if href.startswith('http') and 'jobright.ai' not in href and 'migratemate.co' not in href:
                    return href
                    
        except Exception as e:
            log.debug(f"      ❌ Redirect resolution error: {e}")
        return None


# ═══════════════════════════════════════════════════════════
#  1. SIMPLIFY JOBS — GitHub JSON (listings.json)
# ═══════════════════════════════════════════════════════════
class SimplifyScraper:
    """
    Pulls from SimplifyJobs/New-Grad-Positions GitHub repo.
    The repo has a structured JSON file at:
    .github/scripts/listings.json
    Each entry has: title, company_name, url, locations[], sponsorship, 
    date_posted (unix timestamp), active, is_visible, category
    """
    REPOS = [
        ("SimplifyJobs", "New-Grad-Positions", "dev"),
    ]

    def fetch(self, query=None, should_continue=None, resume_state=None, progress_callback=None):
        jobs = []
        resume_state = resume_state or {}
        done_repos = set(resume_state.get('done_repos', []))
        for org, repo, branch in self.REPOS:
            if repo in done_repos:
                continue
            repo_jobs = []
            url = f"https://raw.githubusercontent.com/{org}/{repo}/refs/heads/{branch}/.github/scripts/listings.json"
            try:
                log.info(f"    📥 Fetching Simplify: {org}/{repo}")
                time.sleep(random.uniform(1.0, 2.0)) # Delay to prevent bot detection
                resp = get_with_retry(scraper, url, timeout=30, attempts=3)
                if not resp:
                    continue
                if resp.status_code != 200:
                    log.warning(f"    ⚠️ Simplify {repo} returned {resp.status_code}")
                    continue

                data = json.loads(resp.text)
                log.info(f"    ← Simplify {repo}: {len(data)} total listings")

                for item in data:
                    # Only active and visible jobs
                    if not item.get('active', False):
                        continue

                    title = item.get('title', '').strip()
                    company = item.get('company_name', '').strip()
                    apply_url = item.get('url', '').strip()
                    locations = item.get('locations', [])
                    location_str = ', '.join(locations) if locations else 'USA'
                    sponsorship = item.get('sponsorship', '')
                    category = item.get('category', '')

                    # Parse timestamp (Use date_updated if newer than date_posted for freshness)
                    posted_ts = item.get('date_posted', 0)
                    updated_ts = item.get('date_updated', 0)
                    final_ts = max(posted_ts, updated_ts)
                    
                    try:
                        posted_date = datetime.fromtimestamp(final_ts, tz=tz.utc)
                    except Exception:
                        posted_date = None

                    # Determine visa type from sponsorship field
                    visa_type = ''
                    if sponsorship and 'offers sponsorship' in sponsorship.lower():
                        visa_type = 'H-1B'

                    # Detect if it's an internship for engine-level filtering
                    is_intern = 'intern' in title.lower() or 'intern' in category.lower()

                    # Reject empty or internal-only URLs at ingestion
                    if not apply_url:
                        continue
                    # Block simplify.jobs internal redirects and github raw URLs
                    apply_url_lower = apply_url.lower()
                    if any(d in apply_url_lower for d in ['simplify.jobs', 'github.com/SimplifyJobs']):
                        continue

                    job_obj = {
                        'source': f'Simplify/{repo}',
                        'source_job_id': item.get('id', ''),
                        'title': title,
                        'company': company,
                        'location': location_str,
                        'description': f"{title} at {company}. Category: {category}. Sponsorship: {sponsorship}.",
                        'external_apply_link': apply_url,
                        'employment_type': 'Internship' if is_intern else 'Full-time',
                        'salary_range': '',
                        'company_logo': '',
                        'posted_date': posted_date,
                        'visa_type': visa_type,
                    }
                    jobs.append(job_obj)
                    repo_jobs.append(job_obj)

            except Exception as e:
                log.error(f"    ❌ Simplify {repo} error: {e}")
            done_repos.add(repo)
            if progress_callback:
                progress_callback({'done_repos': sorted(done_repos)})
            print(f"{repo} -> jobs: {len(repo_jobs)}")
            print(f"{repo} -> pages fetched: 1")
            if should_continue and not should_continue():
                break

        log.info(f"    ✅ Simplify total active: {len(jobs)}")
        return jobs


# ═══════════════════════════════════════════════════════════
#  2. JOBRIGHT.AI — GitHub Markdown Tables (README.md)
# ═══════════════════════════════════════════════════════════
class JobrightScraper:
    """
    Pulls from jobright-ai GitHub repos.
    Each repo has a README.md with markdown tables of jobs.
    Format: | Company | Job Title | Location | Apply Link | Date |
    """
    # All 36 repos from jobright-ai (Internships + New Grad)
    REPOS = [
        # Major Master List
        "Daily-H1B-Jobs-In-Tech",
        # Internships
        "2026-Software-Engineer-Internship",
        "2026-Data-Analysis-Internship",
        "2026-Engineer-Internship",
        "2026-Product-Management-Internship",
        "2026-Design-Internship",
        "2026-Business-Analyst-Internship",
        "2026-Marketing-Internship",
        "2026-Account-Internship",
        "2026-Sales-Internship",
        "2026-HR-Internship",
        "2026-Legal-Internship",
        "2026-Education-Internship",
        "2026-Support-Internship",
        "2026-Art-Internship",
        "2026-Management-Internship",
        "2026-Consultant-Internship",
        "2026-Public-Sector-Internship",
        "2026-Finance-Internship",
        "2026-Mechanical-Engineering-Internship",
        # New Grad
        "2026-Software-Engineer-New-Grad",
        "2026-Product-Management-New-Grad",
        "2026-Data-Analysis-New-Grad",
        "2026-Engineering-New-Grad",
        "2026-Business-Analyst-New-Grad",
        "2026-Account-New-Grad",
        "2026-Design-New-Grad",
        "2026-Consultant-New-Grad",
        "2026-Support-New-Grad",
        "2026-Marketing-New-Grad",
        "2026-Education-New-Grad",
        "2026-HR-New-Grad",
        "2026-Legal-New-Grad",
        "2026-Art-New-Grad",
        "2026-Management-New-Grad",
        "2026-Finance-New-Grad",
        "2026-Others-New-Grad",
        "2026-Others-Internship"
    ]

    def fetch(self, query=None, should_continue=None, resume_state=None, progress_callback=None):
        jobs = []
        log.info(f"    🚀 Fetching Jobright repos in parallel...")
        resume_state = resume_state or {}
        done_repos = set(resume_state.get('done_repos', []))
        
        def fetch_repo(repo):
            # Use a fresh scraper per thread for maximum isolation
            s = create_stealth_scraper()
            try:
                # Try 'master' branch by default (most current)
                branch = 'master'
                url = f"https://raw.githubusercontent.com/jobright-ai/{repo}/{branch}/README.md"
                
                resp = get_with_retry(s, url, timeout=25, attempts=3)
                if not resp:
                    print(f"{repo} -> jobs: 0")
                    print(f"{repo} -> pages fetched: 0")
                    return []
                if resp.status_code == 200:
                    repo_jobs = self._parse_markdown_table(resp.text, repo)
                    print(f"{repo} -> jobs: {len(repo_jobs)}")
                    print(f"{repo} -> pages fetched: 1")
                    return repo_jobs
                
                # Fallback to 'main'
                branch = 'main'
                url = f"https://raw.githubusercontent.com/jobright-ai/{repo}/{branch}/README.md"
                resp = get_with_retry(s, url, timeout=25, attempts=3)
                if not resp:
                    print(f"{repo} -> jobs: 0")
                    print(f"{repo} -> pages fetched: 0")
                    return []
                if resp.status_code == 200:
                    repo_jobs = self._parse_markdown_table(resp.text, repo)
                    print(f"{repo} -> jobs: {len(repo_jobs)}")
                    print(f"{repo} -> pages fetched: 1")
                    return repo_jobs
                
                # Fallback to 'master' (Common in older Jobright repos)
                branch = 'master'
                url = f"https://raw.githubusercontent.com/jobright-ai/{repo}/{branch}/README.md"
                resp = get_with_retry(s, url, timeout=25, attempts=3)
                if not resp:
                    print(f"{repo} -> jobs: 0")
                    print(f"{repo} -> pages fetched: 0")
                    return []
                if resp.status_code == 200:
                    repo_jobs = self._parse_markdown_table(resp.text, repo)
                    print(f"{repo} -> jobs: {len(repo_jobs)}")
                    print(f"{repo} -> pages fetched: 1")
                    return repo_jobs
                
                print(f"{repo} -> jobs: 0")
                print(f"{repo} -> pages fetched: 0")
                return []
            except Exception as e:
                log.error(f"    ⚠️ Jobright {repo} skip: {e}")
                print(f"{repo} -> jobs: 0")
                print(f"{repo} -> pages fetched: 0")
                return []

        for repo in self.REPOS:
            if should_continue and not should_continue():
                break
            if repo in done_repos:
                continue
            result = fetch_repo(repo)
            if result:
                jobs.extend(result)
            done_repos.add(repo)
            if progress_callback:
                progress_callback({'done_repos': sorted(done_repos)})
        
        log.info(f"    ✅ Jobright total: {len(jobs)} jobs fetched from GitHub.")
        return jobs

    def _parse_markdown_table(self, md_text, repo_name):
        """Parse markdown table rows into job dicts."""
        jobs = []
        rows = md_text.split('\n')
        col_map = {'title': 1, 'company': 0, 'location': 2} # default indices

        # 1. Identify columns Fuzzy (Role/Title, Company, Location, Date, Link)
        for row in rows:
            if '|' in row and any(x in row.lower() for x in ['company', 'title', 'role', 'location']):
                cols = [c.strip() for c in row.split('|')]
                if cols and not cols[0]: cols = cols[1:]
                if cols and not cols[-1]: cols = cols[:-1]
                for i, h in enumerate(cols):
                    hl = h.lower()
                    if any(x in hl for x in ['role', 'title', 'position']): col_map['title'] = i
                    elif 'company' in hl: col_map['company'] = i
                    elif 'location' in hl: col_map['location'] = i
                    elif 'date' in hl: col_map['date'] = i
                break # Found header

        # 2. Parse data rows
        for row in rows:
            if '---' in row or not '|' in row: continue
            if any(x in row.lower() for x in ['company', 'title', 'role', 'location']): continue
            
            cols = [c.strip() for c in row.split('|')]
            if cols and not cols[0]: cols = cols[1:]
            if cols and not cols[-1]: cols = cols[:-1]
            if len(cols) < 2: continue

            try:
                # Meta extraction
                md_links = re.findall(r'\[[^\]]*\]\((https?://[^\)]+)\)', row)
                raw_urls = re.findall(r'https?://[^\s\|\]\)]+', row)
                apply_link = ""
                for u in (md_links + raw_urls):
                    if 'jobright.ai/jobs/info/' in u: 
                        apply_link = u
                        break
                if not apply_link and md_links: apply_link = md_links[0]

                if not apply_link:
                    continue  # No URL at all — skip this row entirely

                def clean_field(txt):
                    if not txt: return ""
                    txt = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', txt)
                    txt = re.sub(r'<[^>]+>', '', txt)
                    return txt.strip(' *').replace('↳', '').strip()

                title = clean_field(cols[col_map.get('title')] if col_map.get('title', 99) < len(cols) else "")
                company = clean_field(cols[col_map.get('company')] if col_map.get('company', 99) < len(cols) else "")
                location = clean_field(cols[col_map.get('location')] if col_map.get('location', 99) < len(cols) else "")

                if not title or not company: continue

                # Validation & Refinement
                if not location or len(location) > 40 or 'http' in location or any(x in location.lower() for x in ['engineer', 'intern', 'developer']):
                    location = "USA"
                    for c in cols:
                        if any(l in c.lower() for l in ['remote', 'san francisco', 'new york', 'london', 'aus', 'wa', 'ca', 'tx']):
                            location = clean_field(c)
                            break
                
                source_id = hashlib.md5(f"{title}{company}{location}".lower().encode()).hexdigest()[:12]
                jobs.append({
                    'source': 'Jobright',
                    'source_job_id': f"jr-{source_id}",
                    'title': title,
                    'company': company,
                    'location': location or 'USA',
                    'description': f"{title} at {company} in {location or 'USA'}. Source: Jobright.ai ({repo_name})",
                    'external_apply_link': apply_link,
                    'employment_type': 'Internship' if 'internship' in repo_name.lower() or 'intern' in title.lower() else 'Full-time',
                    'posted_date': self._parse_date(cols[col_map.get('date')] if col_map.get('date', 99) < len(cols) else ""),
                    'visa_type': '',
                    'company_logo': ''
                })
            except Exception as e:
                log.debug(f"    ⚠️ Parse row skipped in {repo_name}: {e}")
                continue
        return jobs

    def _parse_date(self, date_str):
        if not date_str:
            return None
        date_str = re.sub(r'[*\u2605]', '', date_str).strip()
        current_year = datetime.now(tz=tz.utc).year
        try:
            # 1. Try "2026-04-25" or "2026-05-06" ISO format
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
                return dt.replace(hour=23, minute=59, second=59, tzinfo=tz.utc)
            
            # 2. Try "Apr 19" or "May 6" or "May 06" format (assume current year)
            for fmt in ["%b %d, %Y", "%b %d", "%B %d", "%d %b", "%d %B"]:
                try:
                    if '%Y' in fmt:
                        dt = datetime.strptime(date_str, fmt)
                    else:
                        dt = datetime.strptime(f"{date_str}, {current_year}", fmt + ", %Y")
                    return dt.replace(hour=23, minute=59, second=59, tzinfo=tz.utc)
                except Exception:
                    continue
            
            # 3. Fallback: try dateutil
            try:
                import dateutil.parser
                dt = dateutil.parser.parse(date_str, default=datetime(current_year, 1, 1))
                return dt.replace(hour=23, minute=59, second=59, tzinfo=tz.utc)
            except Exception:
                pass
                
        except Exception:
            pass
        
        # Last resort: assume today so the job isn't silently dropped
        return datetime.now(tz=tz.utc)


# ═══════════════════════════════════════════════════════════
#  3. MIGRATEMATE — Web Scrape HTML 
# ═══════════════════════════════════════════════════════════
class MigrateMateScraper:
    """
    Scrapes migratemate.co visa sponsorship jobs.
    Pages: /visa-sponsorship-jobs/h1b, /opt, /tn, etc.
    """
    CATEGORIES = [
        # ── General visa pages (5 jobs each) ──
        ('h1b-jobs', 'H-1B'),
        ('opt-jobs', 'OPT/CPT'),
        ('tn-jobs', 'TN'),
        ('green-card-jobs', 'Green Card'),
        ('entry-level-jobs', 'Entry Level'),
        # ── Software Engineering ──
        ('h1b-jobs/software-engineer', 'Software Engineer'),
        ('h1b-jobs/backend-developer', 'Backend Developer'),
        ('h1b-jobs/frontend-developer', 'Frontend Developer'),
        ('h1b-jobs/full-stack-developer', 'Full Stack Developer'),
        ('h1b-jobs/java-developer', 'Java Developer'),
        ('h1b-jobs/python-developer', 'Python Developer'),
        ('h1b-jobs/mobile-developer', 'Mobile Developer'),
        # ── Infrastructure & DevOps ──
        ('h1b-jobs/devops-engineer', 'DevOps Engineer'),
        ('h1b-jobs/cloud-engineer', 'Cloud Engineer'),
        ('h1b-jobs/site-reliability-engineer', 'SRE'),
        # ── Data & AI ──
        ('h1b-jobs/data-analyst', 'Data Analyst'),
        ('h1b-jobs/data-engineer', 'Data Engineer'),
        ('h1b-jobs/data-scientist', 'Data Scientist'),
        ('h1b-jobs/machine-learning-engineer', 'ML Engineer'),
        # ── Management & Business ──
        ('h1b-jobs/product-manager', 'Product Manager'),
        ('h1b-jobs/project-manager', 'Project Manager'),
        ('h1b-jobs/business-analyst', 'Business Analyst'),
        ('h1b-jobs/finance-analyst', 'Finance Analyst'),
        # ── Design & QA ──
        ('h1b-jobs/ux-designer', 'UX Designer'),
        ('h1b-jobs/qa-engineer', 'QA Engineer'),
        # ── Engineering ──
        ('h1b-jobs/mechanical-engineer', 'Mechanical Engineer'),
        ('h1b-jobs/civil-engineer', 'Civil Engineer'),
        ('h1b-jobs/electrical-engineer', 'Electrical Engineer'),
        # ── OPT specific tech ──
        ('opt-jobs/software-engineer', 'OPT Software Engineer'),
        ('opt-jobs/data-analyst', 'OPT Data Analyst'),
        ('opt-jobs/data-engineer', 'OPT Data Engineer'),
    ]

    def fetch(self, query=None, should_continue=None, resume_state=None, progress_callback=None):
        all_jobs = []
        # Scrape ALL categories every pass for maximum coverage
        import random
        selected_cats = list(self.CATEGORIES)  # ALL 12 categories, not just 3
        
        # Select ONE persistent identity for this sync cycle
        ua = random.choice(USER_AGENTS)
        establishment_scraper = create_stealth_scraper()
        establishment_scraper.headers.update({'User-Agent': ua})
        
        try:
            log.info(f"    🏢 Stealth Warmup for MigrateMate...")
            # Step 1: Human-like landing
            establishment_scraper.get("https://migratemate.co/h1b-jobs", timeout=30)
            time.sleep(2) 
        except Exception as e:
            log.warning(f"    ⚠️ MigrateMate warmup failed: {e}")

        resume_state = resume_state or {}
        category_progress = resume_state.get('category_progress', {})
        start_idx = int(resume_state.get('category_index', 0))

        for idx, (slug, cat_name) in enumerate(selected_cats):
            if idx < start_idx:
                continue
            if should_continue and not should_continue():
                break
            try:
                base_url = f"https://migratemate.co/{slug}"
                log.info(f"    📥 Single-Drip Fetch: {cat_name}")
                headers = {
                    'Referer': 'https://migratemate.co/h1b-jobs',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin',
                    'Upgrade-Insecure-Requests': '1',
                }
                cat_state = category_progress.get(slug, {})
                page = int(cat_state.get('next_page', 1))
                page_count = 0
                cat_jobs = 0
                seen_page_signatures = set()
                while True:
                    if should_continue and not should_continue():
                        break
                    url = base_url if page == 1 else f"{base_url}?page={page}"
                    resp = get_with_retry(establishment_scraper, url, timeout=30, headers=headers, attempts=3)
                    if not resp or resp.status_code != 200:
                        if page == 1:
                            log.warning(f"    ⚠️ MigrateMate {slug} block ({resp.status_code if resp else 'no-response'}).")
                        break
                    parsed = self._parse_html(resp.text, cat_name, slug)
                    sig = '|'.join(sorted(j.get('source_job_id', '') for j in parsed if j.get('source_job_id')))
                    if not parsed or sig in seen_page_signatures:
                        break
                    seen_page_signatures.add(sig)
                    all_jobs.extend(parsed)
                    cat_jobs += len(parsed)
                    page_count += 1
                    log.info(f"    ← Stealth success ({cat_name}) page {page}: {len(parsed)} jobs")
                    page += 1
                    category_progress[slug] = {'next_page': page}
                    if progress_callback:
                        progress_callback({'category_index': idx, 'category_progress': category_progress})
                    time.sleep(random.uniform(0.8, 1.8))
                if cat_jobs == 0:
                    fallback_jobs, fallback_pages = self._fallback_category_fetch(
                        establishment_scraper, slug, cat_name, headers
                    )
                    all_jobs.extend(fallback_jobs)
                    cat_jobs += len(fallback_jobs)
                    page_count += fallback_pages
                print(f"{cat_name} -> jobs: {cat_jobs}")
                print(f"{cat_name} -> pages fetched: {page_count}")
                category_progress[slug] = {'next_page': 1}
                if progress_callback:
                    progress_callback({'category_index': idx + 1, 'category_progress': category_progress})
                time.sleep(random.uniform(2, 5)) # Delay between categories
            except Exception as e:
                log.error(f"    ❌ MigrateMate error in {cat_name}: {e}")

        return all_jobs

    def _fallback_category_fetch(self, session, slug, cat_name, headers):
        """Fallback fetch for blocked category pages via parent listing pages."""
        parent_slug = slug.split('/')[0]
        base_url = f"https://migratemate.co/{parent_slug}"
        slug_tokens = [
            t for t in slug.replace('/', '-').split('-')
            if t and t not in {'jobs', 'h1b', 'opt', 'tn', 'green', 'card'}
        ]
        jobs = []
        pages_fetched = 0
        seen_page_signatures = set()

        page = 1
        while True:
            url = base_url if page == 1 else f"{base_url}?page={page}"
            resp = get_with_retry(session, url, timeout=30, headers=headers, attempts=3)
            if not resp or resp.status_code != 200:
                break
            parsed = self._parse_html(resp.text, cat_name, slug)
            if slug_tokens:
                parsed = [
                    j for j in parsed
                    if any(tok in (j.get('title', '') + ' ' + j.get('description', '')).lower() for tok in slug_tokens)
                ]
            sig = '|'.join(sorted(j.get('source_job_id', '') for j in parsed if j.get('source_job_id')))
            if not parsed or sig in seen_page_signatures:
                break
            seen_page_signatures.add(sig)
            jobs.extend(parsed)
            pages_fetched += 1
            page += 1
            time.sleep(random.uniform(0.6, 1.2))

        if jobs:
            log.info(f"    🔁 Fallback recovered {len(jobs)} jobs for {slug}")
        return jobs, pages_fetched

    def _parse_html(self, html, visa_type, slug):
        """
        Parse MigrateMate job listing HTML.
        Strategy:
          1. Extract individual job page links from HTML job cards (most reliable)
          2. Cross-reference JSON-LD ItemList for metadata (title, company, date, location)
          3. These migratemate.co/job/... URLs redirect to direct ATS pages via LinkResolver
        """
        import json
        import hashlib
        jobs = []
        soup = BeautifulSoup(html, 'html.parser')

        # ── Step 1: Extract individual job links from HTML card elements ──
        # MigrateMate renders job cards as <a href="/job/company-slug/job-slug">
        html_job_links = {}  # title_key -> migratemate_url
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            # Match patterns: /job/..., /h1b-jobs/..., /opt-jobs/..., /jobs/...
            if re.match(r'^/(?:job|h1b-jobs|opt-jobs|tn-jobs|green-card-jobs)/[^/]+/[^/]+', href):
                full_url = f"https://migratemate.co{href}"
                # Extract a title hint from the URL slug
                parts = href.rstrip('/').split('/')
                if len(parts) >= 3:
                    slug_key = parts[-1].replace('-', ' ').lower()
                    if full_url not in html_job_links.values():
                        html_job_links[slug_key] = full_url

        log.info(f"    🔗 MigrateMate HTML links found: {len(html_job_links)}")

        # ── Step 2: Parse JSON-LD for metadata ──
        scripts = soup.find_all('script', type='application/ld+json')
        found_data = False
        
        for s in scripts:
            try:
                script_content = s.text.strip()
                if not script_content: continue
                
                data = json.loads(script_content)
                
                if isinstance(data, dict) and data.get('@type') == 'ItemList':
                    elements = data.get('itemListElement', [])
                    for element in elements:
                        item = element.get('item', {})
                        if item.get('@type') == 'JobPosting':
                            title = item.get('title', '').strip()
                            company_info = item.get('hiringOrganization', {})
                            company = company_info.get('name', 'Unknown').strip()
                            
                            # Location
                            loc_info = item.get('jobLocation', {})
                            if isinstance(loc_info, list) and loc_info:
                                loc_info = loc_info[0]
                            address = loc_info.get('address', {})
                            if isinstance(address, dict):
                                city = address.get('addressLocality', '')
                                state = address.get('addressRegion', '')
                                location = f"{city}, {state}".strip(', ') or 'USA'
                            else:
                                location = 'USA'

                            # ── URL Resolution Priority ──
                            # 1. JSON-LD url field (usually empty on MigrateMate)
                            apply_url = item.get('url', '').strip()
                            
                            # 2. Match via HTML job links using title slug
                            if not apply_url or 'migratemate.co' in apply_url:
                                title_slug = re.sub(r'[^a-z0-9\s]', '', title.lower())
                                title_words = [w for w in title_slug.split() if len(w) > 2]
                                for link_key, link_url in html_job_links.items():
                                    # Match if most title words appear in the slug
                                    matches = sum(1 for w in title_words if w in link_key)
                                    if title_words and matches / len(title_words) >= 0.5:
                                        apply_url = link_url
                                        break
                            
                            # 3. Fallback: category page (will trigger DDG search in resolver)
                            if not apply_url:
                                apply_url = f"https://migratemate.co/{slug}"
                            
                            # Date Posted
                            raw_date = item.get('datePosted')
                            posted_dt = self._parse_iso_date(raw_date)
                            
                            if title and company and apply_url:
                                source_id = hashlib.md5(f"{title}{company}{apply_url}".lower().encode()).hexdigest()[:12]
                                jobs.append({
                                    'source': 'MigrateMate',
                                    'source_job_id': f"mm-{source_id}",
                                    'title': title,
                                    'company': company,
                                    'location': location,
                                    'description': item.get('description', f"{title} at {company}. Source: MigrateMate"),
                                    'external_apply_link': apply_url,
                                    'employment_type': 'Full-time',
                                    'visa_type': visa_type if visa_type in ['H-1B', 'OPT/CPT', 'TN', 'Green Card'] else 'Visa',
                                    'posted_date': posted_dt
                                })
                                found_data = True
                
                if found_data: break
            except Exception as e:
                log.debug(f"      ⚠ JSON-LD parse error: {e}")
                continue

        if not jobs:
            html_snippet = html[:500].lower()
            if not html.strip():
                log.warning("    ⚠️ MigrateMate returned EMPTY HTML (Bot block suspected). Skipping.")
            elif 'cloudflare' in html_snippet or 'datadome' in html_snippet:
                log.warning("    🛡️ MigrateMate bot-protection challenge detected.")
            else:
                log.warning(f"    ⚠️ MigrateMate JSON-LD not found. Structure may have changed.")
            
        return jobs

    def _parse_time_ago(self, text):
        """Parse strings like '2h ago', '1d ago', '3w ago' into datetime."""
        from datetime import datetime, timedelta
        now = datetime.now(tz=tz.utc)
        m = re.search(r'(\d+)([hdwmy])\s*ago', text, re.IGNORECASE)
        if not m:
            return None
        
        val = int(m.group(1))
        unit = m.group(2).lower()
        
        if unit == 'h':
            return now - timedelta(hours=val)
        elif unit == 'd':
            return now - timedelta(days=val)
        elif unit == 'w':
            return now - timedelta(weeks=val)
        elif unit == 'm':
            return now - timedelta(days=val * 30)
        elif unit == 'y':
            return now - timedelta(days=val * 365)
        
        return None

    def _parse_iso_date(self, date_str):
        """Parse ISO date string into aware datetime."""
        if not date_str:
            # Fallback: if no date, assume today to pass 24h filter
            return datetime.now(tz=tz.utc)
        try:
            from dateutil.parser import parse
            dt = parse(date_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=tz.utc)
            return dt
        except:
            return datetime.now(tz=tz.utc)
