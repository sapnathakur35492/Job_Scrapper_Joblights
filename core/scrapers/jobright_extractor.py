"""
Jobright URL Extractor — 7-Step Layered Extraction Engine

Extracts the final job posting URL from a Jobright apply link.
Priority: Direct extraction → HTML/API → Search → ATS → Auth fallback
"""
import os
import re
import json
import time
import base64
import logging
import hashlib
import random
from urllib.parse import urlparse, parse_qs, unquote

import cloudscraper
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger('sociax_sync.extractor')

# ── Stealth scraper setup ──
def _create_scraper():
    s = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
    )
    s.headers.update({
        'Accept-Language': 'en-US,en;q=0.9',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'DNT': '1',
    })
    return s


# ── Known ATS domains ──
ATS_DOMAINS = [
    'workday', 'lever.co', 'greenhouse.io', 'ashbyhq.com', 'breezy.hr',
    'smartrecruiters.com', 'myworkdayjobs.com', 'jobvite.com', 'recruitee.com',
    'personio.', 'taleo.net', 'icims.com', 'workable.com', 'rippling-ats.com',
    'applytojob.com', 'freshteam.com', 'bamboohr.com',
]

BLOCKED_DOMAINS = [
    'jobright.ai', 'google.com', 'linkedin.com', 'facebook.com', 'twitter.com',
    'x.com', 'glassdoor.com', 'indeed.com', 'ziprecruiter.com', 'monster.com',
    'crunchbase.com', 'prnewswire.com', 'businesswire.com', 'instagram.com',
    'youtube.com', 'github.com', 'medium.com',
]

NEWS_FRAGMENTS = [
    '/news/', '/article/', '/press/', '/blog/', '/story/',
    'techcrunch', 'forbes', 'bloomberg', 'reuters', 'venturebeat',
]


def _is_valid_job_url(url):
    """Check if URL looks like a real specific job posting (not social/news/tracking/generic)."""
    if not url or not url.startswith('http'):
        return False
    u = url.lower()
    
    # Block domains
    if any(d in u for d in BLOCKED_DOMAINS):
        return False
        
    # Block news
    if any(f in u for f in NEWS_FRAGMENTS):
        return False
        
    # Block generic file extensions
    if any(ext in u for ext in ['.png', '.jpg', '.svg', '.gif', '.css', '.js', '.pdf']):
        return False
        
    # STRICT MODE: Block generic ATS roots and career pages if they don't look like a specific job path
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    
    # If the path is just empty or very short, it's a homepage/board, not a job
    if not path or path == '/' or path == '/careers' or path == '/jobs' or path == '/about' or path == '/company':
        return False

    # Block support and help articles from ATS
    if 'support.greenhouse.io' in u or 'help.lever.co' in u or 'support.workday.com' in u:
        return False

    # Reject generic job boards (they need an ID or slug)
    # Check if the path contains numbers, dashes (slugs), or UUIDs
    has_identifier = bool(re.search(r'\d+|-[a-z0-9]+-[a-z0-9]+', path))

    if 'lever.co' in parsed.netloc and not has_identifier:
        return False
    if 'greenhouse.io' in parsed.netloc and ('/jobs/' not in path and '/job/' not in path and not has_identifier):
        return False
    if 'workdayjobs.com' in parsed.netloc and '/job/' not in path:
        return False
    if 'bamboohr.com' in parsed.netloc and '/careers/' not in path and not has_identifier:
        return False

    return True


def _is_valid_company_url(url):
    """Permissive check: accepts company homepages and careers pages (not just specific job postings).
    Used as fallback when we have the company site but can't find a specific job URL."""
    if not url or not url.startswith('http'):
        return False
    u = url.lower()
    # Block social/aggregator sites
    if any(d in u for d in BLOCKED_DOMAINS):
        return False
    # Block file resources
    if any(ext in u for ext in ['.png', '.jpg', '.svg', '.gif', '.css', '.js', '.pdf']):
        return False
    # Block news/blog sites
    if any(f in u for f in NEWS_FRAGMENTS):
        return False
    return True


def _is_ats_url(url):
    """Check if URL belongs to a known ATS platform."""
    u = url.lower()
    return any(ats in u for ats in ATS_DOMAINS)


def _normalize_company(name):
    """Normalize company name for URL generation."""
    if not name:
        return ''
    return re.sub(r'[^a-z0-9]', '', name.lower())


class JobrightURLExtractor:
    """
    7-step layered extraction engine for Jobright apply URLs.
    Each step has a 2-4s timeout. Total request ≤ 10s target.
    """

    def __init__(self):
        self.scraper = _create_scraper()
        self._job_title = None
        self._company = None
        self._company_url = None  # Company website URL (fallback for Step 5)
        self._steps_attempted = []

    def extract(self, input_url):
        """
        Main entry point. Returns structured result dict.
        Follows strict priority: Step1 → Step2 → ... → Step7
        """
        start_time = time.time()
        input_url = (input_url or '').strip()

        if not input_url:
            return self._fail('Empty URL provided', 'validation')

        log.info(f"🔍 Extracting URL: {input_url}")

        # Parse the job ID from the URL
        self._job_id = self._extract_job_id(input_url)

        steps = [
            ('step1_direct_url_extraction', self._step1_direct_url_extraction),
            ('step2_html_inspection', self._step2_html_inspection),
            ('step3_public_api_detection', self._step3_public_api_detection),
            ('step4_job_data_extraction', self._step4_job_data_extraction),
            ('step5_search_reconstruction', self._step5_search_reconstruction),
            ('step6_authenticated_fallback', self._step6_authenticated_fallback),
        ]

        # Step 4 is data-only (feeds Steps 5-6), not a URL-returning step
        for step_name, step_fn in steps:
            self._steps_attempted.append(step_name)
            try:
                log.info(f"  ▶ {step_name}...")
                result_url = step_fn(input_url)
                # Step 5 company-URL fallback uses a permissive validator (accepts homepages)
                if step_name == 'step5_search_reconstruction':
                    url_ok = result_url and _is_valid_company_url(result_url)
                else:
                    url_ok = result_url and _is_valid_job_url(result_url)
                if url_ok:
                    elapsed = round(time.time() - start_time, 2)
                    confidence = self._get_confidence(step_name)
                    log.info(f"  ✅ Found via {step_name} in {elapsed}s: {result_url[:80]}")
                    return {
                        'status': 'success',
                        'input_url': input_url,
                        'final_url': result_url,
                        'method': step_name,
                        'job_title': self._job_title or '',
                        'company': self._company or '',
                        'confidence': confidence,
                        'reason': None,
                        'time_taken': elapsed,
                        'steps_attempted': self._steps_attempted,
                    }
            except Exception as e:
                log.warning(f"  ⚠ {step_name} error: {e}")
                continue

        elapsed = round(time.time() - start_time, 2)
        log.info(f"  ❌ All steps failed in {elapsed}s")
        return self._fail(
            'No external URL found after all extraction steps',
            self._steps_attempted[-1] if self._steps_attempted else 'none',
            input_url, elapsed
        )

    def _fail(self, reason, method, input_url='', elapsed=0):
        return {
            'status': 'failed',
            'input_url': input_url,
            'final_url': None,
            'method': method,
            'job_title': self._job_title or '',
            'company': self._company or '',
            'confidence': 0.0,
            'reason': reason,
            'time_taken': elapsed,
            'steps_attempted': self._steps_attempted,
        }

    def _get_confidence(self, step_name):
        scores = {
            'step1_direct_url_extraction': 1.0,
            'step2_html_inspection': 0.95,
            'step3_public_api_detection': 0.95,
            'step5_search_reconstruction': 0.7,
            'step6_ats_pattern_matching': 0.65,
            'step7_authenticated_fallback': 1.0,
        }
        return scores.get(step_name, 0.5)

    def _extract_job_id(self, url):
        m = re.search(r'/jobs/info/([a-f0-9]+)', url)
        return m.group(1) if m else ''

    # ═══════════════════════════════════════════════════════
    #  STEP 1: Direct URL Extraction (params, base64)
    # ═══════════════════════════════════════════════════════
    def _step1_direct_url_extraction(self, url):
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Check common redirect params
        for key in ['url', 'redirect', 'target', 'redirect_url', 'dest', 'next', 'return_url']:
            vals = params.get(key, [])
            for v in vals:
                decoded = unquote(v)
                if _is_valid_job_url(decoded):
                    return decoded

        # Check for base64-encoded params
        for key, vals in params.items():
            for v in vals:
                try:
                    decoded = base64.b64decode(v).decode('utf-8', errors='ignore')
                    if decoded.startswith('http') and _is_valid_job_url(decoded):
                        return decoded
                except Exception:
                    pass

        # Check URL path fragments for encoded URLs
        path = unquote(parsed.path)
        urls_in_path = re.findall(r'(https?://[^\s&]+)', path)
        for u in urls_in_path:
            if _is_valid_job_url(u):
                return u

        return None

    # ═══════════════════════════════════════════════════════
    #  STEP 2: HTML Inspection (unauthenticated GET)
    # ═══════════════════════════════════════════════════════
    def _step2_html_inspection(self, url):
        try:
            resp = self.scraper.get(url, timeout=6)
            if resp.status_code != 200:
                return None
        except Exception:
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')
        self._soup_cache = soup

        # ── 2a: PRIORITY — Parse Jobright helper JSON (most reliable source) ──
        # Jobright embeds <script id="jobright-helper-job-detail-info" type="application/json">
        # with full job data: jobTitle, companyName, companyURL, isCompanySiteLink, etc.
        helper_tag = soup.find('script', id='jobright-helper-job-detail-info')
        if helper_tag:
            try:
                hdata = json.loads(helper_tag.string or '{}')
                job_result = hdata.get('jobResult', {})
                company_result = hdata.get('companyResult', {})

                # Extract title and company for later steps
                self._job_title = self._job_title or job_result.get('jobTitle') or job_result.get('jobNlpTitle')
                self._company = self._company or company_result.get('companyName') or job_result.get('company')
                # Store company website URL for fallback use in Step 5
                company_url = company_result.get('companyURL', '')
                if company_url and company_url.startswith('http'):
                    self._company_url = company_url  # e.g. https://www.spacex.com
                    log.info(f"    🏢 Company URL from helper JSON: {company_url}")

                # Check if job has a direct company site apply link
                is_company_site = job_result.get('isCompanySiteLink', False)
                log.info(f"    📋 isCompanySiteLink={is_company_site}, title={self._job_title}, company={self._company}")
            except Exception as e:
                log.debug(f"    ⚠ Helper JSON parse error: {e}")

        # ── 2b: JSON-LD structured data (job-posting schema) ──
        for script in soup.find_all('script', id='job-posting', type='application/ld+json'):
            try:
                data = json.loads(script.string or '{}')
                # Extract title/company from schema
                self._job_title = self._job_title or data.get('title')
                org = data.get('hiringOrganization') or {}
                self._company = self._company or org.get('name')
                # sameAs is company website, not specific job URL — store for fallback
                same_as = org.get('sameAs', '')
                if same_as and same_as.startswith('http') and not hasattr(self, '_company_url'):
                    self._company_url = same_as
                # The schema url/sameAs is usually just company homepage, skip as apply link
            except Exception:
                pass

        # ── 2c: Scan for "Apply on Employer Site" anchor links ──
        # Jobright renders this as a visible link: "Apply on Employer Site" or "APPLY NOW"
        apply_keywords = ['apply on employer', 'apply on company', 'apply now', 'apply at', 'apply here']
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            text = a.get_text(strip=True).lower()
            if any(kw in text for kw in apply_keywords):
                if href.startswith('http') and 'jobright.ai' not in href:
                    if _is_valid_job_url(href):
                        log.info(f"    ✅ Found apply anchor '{a.get_text(strip=True)}': {href}")
                        return href

        # ── 2d: __NEXT_DATA__ extraction (Jobright is Next.js) ──
        next_data_tag = soup.find('script', id='__NEXT_DATA__')
        if next_data_tag:
            try:
                ndata = json.loads(next_data_tag.string or '{}')
                result = self._extract_from_next_data(ndata)
                if result:
                    return result
            except Exception:
                pass

        # ── 2e: Scan all anchor tags for ATS/career links ──
        candidates = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if not href.startswith('http') or 'jobright.ai' in href:
                continue
            if _is_valid_job_url(href):
                if _is_ats_url(href):
                    log.info(f"    ✅ Found ATS link in page: {href[:60]}")
                    return href
                if any(kw in href.lower() for kw in ['/job/', '/jobs/', '/apply', '/careers/', 'career.']):
                    candidates.append(href)

        if candidates:
            return candidates[0]

        return None

    def _extract_from_next_data(self, data):
        """Recursively search __NEXT_DATA__ for valid job URLs."""
        candidates = []

        def _recurse(obj):
            if isinstance(obj, str):
                if obj.startswith('http') and _is_valid_job_url(obj):
                    candidates.append(obj)
                # Try to extract job title and company
            elif isinstance(obj, dict):
                # Look for specific keys that might hold the external URL
                for key in ['applyUrl', 'apply_url', 'externalUrl', 'external_url',
                            'companyUrl', 'jobUrl', 'url', 'link', 'applicationUrl']:
                    val = obj.get(key)
                    if isinstance(val, str) and val.startswith('http') and _is_valid_job_url(val):
                        candidates.append(val)

                # Extract title/company metadata
                for tk in ['title', 'jobTitle', 'job_title', 'positionTitle']:
                    if obj.get(tk) and isinstance(obj[tk], str) and len(obj[tk]) > 3:
                        self._job_title = self._job_title or obj[tk]
                for ck in ['company', 'companyName', 'company_name', 'employer', 'organizationName']:
                    if obj.get(ck) and isinstance(obj[ck], str) and len(obj[ck]) > 1:
                        self._company = self._company or obj[ck]

                for v in obj.values():
                    _recurse(v)
            elif isinstance(obj, list):
                for i in obj:
                    _recurse(i)

        _recurse(data)

        if not candidates:
            return None

        # Score and rank
        def score(u):
            ul = u.lower()
            s = 0
            if _is_ats_url(ul):
                s += 100
            if any(kw in ul for kw in ['/job/', '/jobs/', '/apply', '/careers/']):
                s += 50
            if any(nw in ul for nw in NEWS_FRAGMENTS):
                s -= 80
            s += min(len(u) / 10, 10)
            return s

        ranked = sorted(candidates, key=score, reverse=True)
        best = ranked[0]
        if score(best) > 10:
            return best
        return None

    # ═══════════════════════════════════════════════════════
    #  STEP 3: Public API Detection
    # ═══════════════════════════════════════════════════════
    def _step3_public_api_detection(self, url):
        if not self._job_id:
            return None

        api_patterns = [
            f"https://jobright.ai/api/job/{self._job_id}",
            f"https://jobright.ai/api/v1/jobs/{self._job_id}",
            f"https://jobright.ai/api/v2/jobs/{self._job_id}",
            f"https://jobright.ai/api/jobPosting/{self._job_id}",
            f"https://jobright.ai/api/public/job/{self._job_id}",
        ]

        for api_url in api_patterns:
            try:
                resp = self.scraper.get(api_url, timeout=3)
                if resp.status_code == 200:
                    data = resp.json()
                    # Try to find URL in response
                    for key in ['url', 'apply_url', 'external_url', 'redirect_url', 'link']:
                        val = data.get(key)
                        if val and _is_valid_job_url(val):
                            self._job_title = self._job_title or data.get('title')
                            self._company = self._company or data.get('company')
                            return val
            except Exception:
                continue
        return None

    # ═══════════════════════════════════════════════════════
    #  STEP 4: Job Data Extraction (title + company)
    # ═══════════════════════════════════════════════════════
    def _step4_job_data_extraction(self, url):
        """Extract job title and company for Steps 5-6. Does NOT return a URL."""
        # Try from cached soup
        soup = getattr(self, '_soup_cache', None)
        if soup:
            # Title from <title> tag
            title_tag = soup.find('title')
            if title_tag:
                text = title_tag.get_text(strip=True)
                # Pattern: "Title @ Company | Jobright.ai"
                m = re.match(r'^(.+?)\s*[@|]\s*(.+?)(?:\s*\||\s*-|\s*—)\s*Jobright', text, re.I)
                if m:
                    self._job_title = self._job_title or m.group(1).strip()
                    self._company = self._company or m.group(2).strip()

            # OG title
            og_title = soup.find('meta', attrs={'property': 'og:title'})
            if og_title:
                content = og_title.get('content', '')
                m = re.match(r'^(.+?)\s*[@|]\s*(.+?)(?:\s*\|)', content, re.I)
                if m:
                    t, c = m.group(1).strip(), m.group(2).strip()
                    if t != 'undefined':
                        self._job_title = self._job_title or t
                    if c != 'undefined':
                        self._company = self._company or c

            # OG description
            og_desc = soup.find('meta', attrs={'property': 'og:description'})
            if og_desc:
                content = og_desc.get('content', '')
                m = re.search(r'Apply to (.+?) at (.+?) on Jobright', content, re.I)
                if m:
                    t, c = m.group(1).strip(), m.group(2).strip()
                    if t != 'undefined':
                        self._job_title = self._job_title or t
                    if c != 'undefined':
                        self._company = self._company or c

        # Try DB lookup if we have the job ID
        if not self._job_title or not self._company:
            try:
                from core.models import Job
                if self._job_id:
                    job = Job.objects.filter(external_apply_link__icontains=self._job_id).first()
                    if job:
                        self._job_title = self._job_title or job.title
                        self._company = self._company or job.company
            except Exception:
                pass

        log.info(f"    📋 Title: {self._job_title}, Company: {self._company}")
        # This step doesn't return a URL — it feeds Steps 5+6
        return None

    # ═══════════════════════════════════════════════════════
    #  STEP 5: Search Reconstruction (multi-query)
    # ═══════════════════════════════════════════════════════
    def _step5_search_reconstruction(self, url):
        if not self._job_title or not self._company:
            return None
        if self._job_title == 'undefined' or self._company == 'undefined':
            return None

        # Clean titles for search (remove special chars)
        clean_title = re.sub(r'[^a-zA-Z0-9\s]', ' ', self._job_title).strip()
        clean_company = re.sub(r'[^a-zA-Z0-9\s]', ' ', self._company).strip()

        # If we have the company website, build site:-scoped ATS queries first
        company_domain = ''
        company_url = self._company_url or ''
        if company_url:
            try:
                company_domain = urlparse(company_url).netloc.replace('www.', '')
            except Exception:
                pass

        queries = []
        # Priority 1: ATS-targeted search with company name
        queries.append(f'site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com "{clean_company}" "{clean_title}"')
        # Priority 2: Company domain + job title (if we have company URL)
        if company_domain:
            queries.append(f'site:{company_domain} "{clean_title}" apply')
        # Priority 3: General search with ATS keywords
        queries.append(f'{clean_company} {clean_title} greenhouse lever workday careers apply')
        # Priority 4: Simple fallback
        queries.append(f'{clean_title} {clean_company} job apply careers')

        for query in queries:
            for attempt in range(2):  # Max 2 retries per query
                try:
                    result = self._web_search(query)
                    if result:
                        log.info(f"    🔍 Search hit via: {query[:60]}")
                        return result
                    break  # No result but no error — skip retries
                except Exception as e:
                    log.debug(f"    🔄 Search retry {attempt+1}: {e}")
                    time.sleep(random.uniform(1, 2))
                    continue

        # ── Step 5 Fallback: Use company URL as last resort ──
        # When ATS search fails but we have the company's careers page URL,
        # return the company homepage as the apply destination.
        if company_url:
            log.info(f"    🏢 Using company homepage as fallback apply URL: {company_url}")
            # Build likely careers page URL
            careers_candidates = [
                company_url.rstrip('/') + '/careers',
                company_url.rstrip('/') + '/jobs',
                company_url.rstrip('/') + '/career',
            ]
            # Try each careers URL via a quick HTTP check
            for careers_url in careers_candidates:
                try:
                    r = self.scraper.head(careers_url, timeout=3, allow_redirects=True)
                    if r.status_code < 400:
                        log.info(f"    ✅ Careers page confirmed: {careers_url}")
                        return careers_url
                except Exception:
                    continue
            # If none respond, return base company URL
            return company_url

        return None

    def _web_search(self, query):
        """Perform a web search to find the ATS link, using multiple engines for reliability."""
        # 1. Try Google Search first (via googlesearch-python)
        try:
            from googlesearch import search
            for url in search(query, num_results=5, sleep_interval=1):
                if not url: continue
                if _is_valid_job_url(url):
                    if _is_ats_url(url) or any(kw in url.lower() for kw in ['/job/', '/jobs/', '/apply', '/careers/', '/posting/']):
                        return url
        except Exception as e:
            log.debug(f"    ⚠ Google Search failed: {e}")

        # 2. Try Custom Yahoo Search (Very reliable, rarely rate-limits)
        try:
            url = 'https://search.yahoo.com/search?p=' + urllib.parse.quote(query)
            resp = self.scraper.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'})
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    # Yahoo wraps URLs in a redirect like: /RU=https%3a%2f%2fcareers.com/...
                    if 'RU=' in href:
                        try:
                            extracted_url = urllib.parse.unquote(href.split('RU=')[1].split('/')[0])
                            if _is_valid_job_url(extracted_url):
                                if _is_ats_url(extracted_url) or any(kw in extracted_url.lower() for kw in ['/job/', '/jobs/', '/apply', '/careers/', '/posting/']):
                                    log.info(f"    🔍 Yahoo hit: {extracted_url[:60]}")
                                    return extracted_url
                        except Exception:
                            pass
        except Exception as e:
            log.debug(f"    ⚠ Yahoo Search failed: {e}")

        # 3. Fallback to DuckDuckGo (via ddgs)
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
                for res in results:
                    url = res.get('href')
                    if url and _is_valid_job_url(url):
                        if _is_ats_url(url) or any(kw in url.lower() for kw in ['/job/', '/jobs/', '/apply', '/careers/', '/posting/']):
                            return url
        except Exception as e:
            log.debug(f"    ⚠ DuckDuckGo Search failed: {e}")

        return None

    # ═══════════════════════════════════════════════════════
    #  STEP 6: Authenticated Fallback
    # ═══════════════════════════════════════════════════════
    def _step6_authenticated_fallback(self, url):
        session_cookie = os.getenv('JOBRIGHT_SESSION_COOKIE', '').strip()
        auth_token = os.getenv('JOBRIGHT_AUTH_TOKEN', '').strip()

        if not session_cookie and not auth_token:
            log.info("    ⏭ No auth credentials configured — skipping Step 7")
            return None

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            cookies = {}

            if session_cookie:
                # Parse cookie string: "key1=val1; key2=val2"
                for part in session_cookie.split(';'):
                    part = part.strip()
                    if '=' in part:
                        k, v = part.split('=', 1)
                        cookies[k.strip()] = v.strip()

            if auth_token:
                headers['Authorization'] = f'Bearer {auth_token}'

            # Use requests directly (not cloudscraper) for clean redirect tracking
            session = requests.Session()
            session.headers.update(headers)
            session.cookies.update(cookies)

            resp = session.get(url, timeout=4, allow_redirects=True)

            # Check the redirect chain for external URLs
            if resp.history:
                for r in resp.history:
                    loc = r.headers.get('Location', '')
                    if loc and _is_valid_job_url(loc):
                        return loc

            # Check final URL
            if resp.url and _is_valid_job_url(resp.url):
                return resp.url

            # Parse the authenticated page HTML
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                # Check __NEXT_DATA__ with auth data
                next_data = soup.find('script', id='__NEXT_DATA__')
                if next_data:
                    try:
                        ndata = json.loads(next_data.string or '{}')
                        result = self._extract_from_next_data(ndata)
                        if result:
                            return result
                    except Exception:
                        pass

                # Check for apply buttons
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    text = a.get_text(strip=True).lower()
                    if ('apply' in text or 'external' in text) and _is_valid_job_url(href):
                        return href

        except Exception as e:
            log.warning(f"    ⚠ Auth fallback error (expired session?): {e}")

        return None


# ── Convenience function ──
def extract_jobright_url(input_url):
    """Single-call convenience function."""
    extractor = JobrightURLExtractor()
    return extractor.extract(input_url)


def extract_jobright_urls_batch(urls):
    """Batch extraction for multiple URLs."""
    results = []
    for url in urls:
        extractor = JobrightURLExtractor()
        results.append(extractor.extract(url))
    return results
