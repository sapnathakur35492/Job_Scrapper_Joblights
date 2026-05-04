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
                    future_to_job[executor.submit(cls.resolve_single, link, session)] = job
            
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
    def resolve_single(cls, url, session):
        """Resolves a single intermediate link."""
        try:
            # Handle Jobright links using the new extractor engine
            if 'jobright.ai/jobs/info/' in url:
                from core.scrapers.jobright_extractor import extract_jobright_url
                result = extract_jobright_url(url)
                if result and result.get('status') == 'success':
                    log.info(f"      ✨ Jobright extracted: {result.get('final_url')[:50]}...")
                    return result.get('final_url')
                return None

            # Handle MigrateMate and others
            # Random delay to be nice
            time.sleep(random.uniform(0.5, 1.5))
            
            resp = session.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            
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
                    
        except Exception:
            pass
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

    def fetch(self, query=None):
        jobs = []
        for org, repo, branch in self.REPOS:
            url = f"https://raw.githubusercontent.com/{org}/{repo}/refs/heads/{branch}/.github/scripts/listings.json"
            try:
                log.info(f"    📥 Fetching Simplify: {org}/{repo}")
                time.sleep(random.uniform(1.0, 2.0)) # Delay to prevent bot detection
                resp = scraper.get(url, timeout=30)
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

                    jobs.append({
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
                    })

            except Exception as e:
                log.error(f"    ❌ Simplify {repo} error: {e}")

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

    def fetch(self, query=None):
        jobs = []
        log.info(f"    🚀 Fetching Jobright repos in parallel...")
        
        def fetch_repo(repo):
            # Use a fresh scraper per thread for maximum isolation
            s = create_stealth_scraper()
            try:
                # Try 'master' branch by default (most current)
                branch = 'master'
                url = f"https://raw.githubusercontent.com/jobright-ai/{repo}/{branch}/README.md"
                
                resp = s.get(url, timeout=25)
                if resp.status_code == 200:
                    return self._parse_markdown_table(resp.text, repo)
                
                # Fallback to 'main'
                branch = 'main'
                url = f"https://raw.githubusercontent.com/jobright-ai/{repo}/{branch}/README.md"
                resp = s.get(url, timeout=25)
                if resp.status_code == 200:
                    return self._parse_markdown_table(resp.text, repo)
                
                # Fallback to 'master' (Common in older Jobright repos)
                branch = 'master'
                url = f"https://raw.githubusercontent.com/jobright-ai/{repo}/{branch}/README.md"
                resp = s.get(url, timeout=25)
                if resp.status_code == 200:
                    return self._parse_markdown_table(resp.text, repo)
                
                return []
            except Exception as e:
                log.debug(f"    ⚠️ Jobright {repo} skip: {e}")
                return []

        # Concurrency for speed
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_repo = {executor.submit(fetch_repo, r): r for r in self.REPOS}
            for future in as_completed(future_to_repo):
                result = future.result()
                if result:
                    jobs.extend(result)
        
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
                    'source': f'Jobright/{repo_name}',
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
            except Exception: continue
        return jobs

    def _parse_date(self, date_str):
        if not date_str:
            return None
        date_str = date_str.strip(' *')
        try:
            # 1. Try "2026-04-25" format
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return dt.replace(hour=23, minute=59, second=59, tzinfo=tz.utc)
            
            # 2. Try "Apr 19" format (assume current year)
            dt = datetime.strptime(f"{date_str}, 2026", "%b %d, %Y")
            return dt.replace(hour=23, minute=59, second=59, tzinfo=tz.utc)
        except Exception:
            try:
                # 3. Try "19 Apr" format
                dt = datetime.strptime(f"{date_str}, 2026", "%d %b, %Y")
                return dt.replace(hour=23, minute=59, second=59, tzinfo=tz.utc)
            except Exception:
                return None


# ═══════════════════════════════════════════════════════════
#  3. MIGRATEMATE — Web Scrape HTML 
# ═══════════════════════════════════════════════════════════
class MigrateMateScraper:
    """
    Scrapes migratemate.co visa sponsorship jobs.
    Pages: /visa-sponsorship-jobs/h1b, /opt, /tn, etc.
    """
    CATEGORIES = [
        ('h1b', 'H-1B'),
        ('opt', 'OPT/CPT'),
        ('tn', 'TN'),
        ('green-card', 'Green Card'),
        ('software-engineer', 'Software Engineer'),
        ('mechanical-engineer', 'Mechanical Engineer'),
        ('product-manager', 'Product Manager'),
        ('marketing-manager', 'Marketing Manager'),
        ('civil-engineer', 'Civil Engineer'),
        ('data-analyst', 'Data Analyst'),
        ('business-analyst', 'Business Analyst'),
        ('finance-analyst', 'Finance Analyst'),
    ]

    def fetch(self, query=None):
        jobs = []
        # ULTRA-STEALTH: Only scrape ONE category per sync run to be 100% invisible.
        # This prevents MigrateMate's firewall from seeing "bursty" behavior.
        import random
        slug, cat_name = random.choice(self.CATEGORIES)
        
        # Select ONE persistent identity for this sync cycle
        ua = random.choice(USER_AGENTS)
        establishment_scraper = create_stealth_scraper()
        establishment_scraper.headers.update({'User-Agent': ua})
        
        try:
            log.info(f"    🏢 Stealth Warmup for {cat_name}...")
            # Step 1: Human-like landing (REDUCED TIMEOUT)
            establishment_scraper.get("https://migratemate.co/", timeout=10)
            time.sleep(3) 
        except:
            pass

        try:
            url = f"https://migratemate.co/visa-sponsorship-jobs/{slug}"
            log.info(f"    📥 Single-Drip Fetch: {cat_name}")
            
            resp = establishment_scraper.get(url, timeout=10, headers={
                'Referer': 'https://migratemate.co/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Upgrade-Insecure-Requests': '1',
            })
            
            if resp.status_code != 200:
                log.warning(f"    ⚠️ MigrateMate {slug} block ({resp.status_code}). Next sync will retry a different category.")
                return []

            parsed = self._parse_html(resp.text, cat_name)
            jobs.extend(parsed)
            
            log.info(f"    ← Stealth success ({cat_name}): {len(parsed)} jobs")

        except Exception as e:
            log.error(f"    ❌ MigrateMate stealth error: {e}")

        return jobs

    def _parse_html(self, html, visa_type):
        """Parse MigrateMate job listing HTML based on updated structure."""
        jobs = []
        soup = BeautifulSoup(html, 'html.parser')

        # Updated selector: Job cards are rounded-xl containers
        cards = soup.select('div.rounded-xl')
        if not cards:
            # Fallback to older selector if structure varies
            cards = soup.select('a[href*="/jobs/"], .job-card')

        for card in cards:
            try:
                # The site uses a flex structure: logo then a text div
                # text_container = card.find('div', class_=re.compile(r'flex.*flex-col'))
                # Based on browser agent: card -> flex -> div(logo), div(text)
                
                # Heuristic: find the div with most text that isn't the whole card
                text_divs = card.find_all('div', recursive=False)
                if len(text_divs) >= 2:
                    content_div = text_divs[1]
                else:
                    content_div = card

                # According to browser agent report: 
                # Company: :nth-child(1), Title: :nth-child(2), Location: :nth-child(3)
                inner_divs = content_div.find_all('div', recursive=False)
                
                # Check for date (e.g. "2h ago", "1d ago")
                # Usually sits at the bottom or top of the content_div
                date_val = None
                card_text = card.get_text(separator=' ', strip=True)
                posted_date = self._parse_time_ago(card_text)

                if len(inner_divs) >= 2:
                    company = inner_divs[0].get_text(strip=True)
                    title = inner_divs[1].get_text(strip=True)
                    location = inner_divs[2].get_text(strip=True) if len(inner_divs) > 2 else 'USA'
                else:
                    # Fallback to basic text search
                    full_text = card.get_text(separator='|', strip=True)
                    parts = full_text.split('|')
                    if len(parts) >= 2:
                        company = parts[0]
                        title = parts[1]
                        location = parts[2] if len(parts) > 2 else 'USA'
                    else:
                        continue

                # Get the link - typically the card itself is wrapped in an 'a' or contains one
                link_tag = card.find('a') if card.name != 'a' else card
                if link_tag:
                    href = link_tag.get('href', '')
                    apply_link = href if href.startswith('http') else f"https://migratemate.co{href}"
                else:
                    continue

                if not title or len(title) < 3:
                    continue

                # Stable ID using MD5 (Python's hash() is unstable across processes)
                raw_id = f"mm-{company}-{title}".lower()
                stable_id = hashlib.md5(raw_id.encode()).hexdigest()[:12]

                jobs.append({
                    'source': 'MigrateMate',
                    'source_job_id': f"mm-{stable_id}",
                    'title': title,
                    'company': company or 'Unknown',
                    'location': location or 'USA',
                    'description': f"{title} at {company}. Category: {visa_type}. Source: MigrateMate.co",
                    'external_apply_link': apply_link,
                    'employment_type': 'Full-time',
                    'salary_range': '',
                    'company_logo': '',
                    'posted_date': posted_date,
                    'visa_type': visa_type if visa_type in ['H-1B', 'OPT/CPT', 'TN', 'Green Card'] else 'Visa',
                })
            except Exception as e:
                continue

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
