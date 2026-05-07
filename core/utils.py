import re
import hashlib
from datetime import datetime
from urllib.parse import urlparse
import cloudscraper
import time
import random
from bs4 import BeautifulSoup
import json

scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)
scraper.headers.update({
    'Accept-Language': 'en-US,en;q=0.9',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'DNT': '1',
})

def clean_text(text):
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]*>', ' ', text)
    # Remove extra whitespace
    return ' '.join(text.split())

def is_visa_sponsored(title, description):
    visa_keywords = [
        r'h-?1b', r'opt', r'cpt', r'tn visa', r'green card', r'j-?1', 
        r'visa sponsorship', r'sponsorship available', r'sponsorship provided',
        r'sponsorship is available'
    ]
    content = (title + " " + description).lower()
    found = []
    for kw in visa_keywords:
        if re.search(kw, content):
            found.append(kw.replace(r'?', ''))
    return ", ".join(set(found)) if found else None

def is_entry_level(title, description):
    entry_keywords = [
        r'junior', r'associate', r'entry[ -]level', r'new grad', r'intern', r'apprentice',
        r'0-?1 year', r'1-?2 years', r'0-?3 years', r'0-?5 years', r'years of experience:? [0-5]'
    ]
    exclude_keywords = [
        r'senior', r'lead', r'staff', r'principal', r'vp', r'director', r'manager', r'head of'
    ]
    
    title_lower = title.lower()
    description_lower = description.lower()
    
    # Check for entry level keywords in title or description
    is_entry = False
    for kw in entry_keywords:
        if re.search(kw, title_lower) or re.search(kw, description_lower):
            is_entry = True
            break
            
    # Check for exclusions in title (exclusions in description are tricky as they might list requirements for others)
    for kw in exclude_keywords:
        if re.search(kw, title_lower):
            # Special case: "Junior Product Manager" might be okay, but "Senior" is not.
            if "junior" not in title_lower:
                return False
                
    return is_entry

def clean_location(location):
    if not location:
        return "Remote / Unknown"
    
    # Remove things like `#5997` or `Corp`
    loc = re.sub(r'#\d+', '', location)
    loc = re.sub(r'\bCorp\b', '', loc, flags=re.IGNORECASE)
    
    # If it is US-FL-Orlando pattern
    m = re.search(r'US-([A-Z]{2})-(.*)', loc, re.IGNORECASE)
    if m:
        loc = f"{m.group(2).replace('-', ' ').title()}, {m.group(1).upper()}"
        
    loc = ' '.join(loc.split()).strip(', ')
    return loc

def get_favicon_url(company_name, apply_url=''):
    """Get a high-res favicon URL from the company website or generic domain."""
    domain = ""
    # List of common ATS domains to ignore for favicon checking
    ats_domains = [
        'greenhouse.io', 'lever.co', 'workday.com', 'myworkdayjobs.com',
        'ashbyhq.com', 'icims.com', 'taleo.net', 'bamboohr.com', 'smartrecruiters.com',
        'jobright.ai', 'simplify.jobs', 'migratemate.co'
    ]
    
    if apply_url:
        try:
            netloc = urlparse(apply_url).netloc.lower()
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            
            is_ats = any(ats in netloc for ats in ats_domains)
            if not is_ats and netloc:
                domain = netloc
        except Exception:
            pass
            
    if not domain:
        # Fallback: synthesize a .com domain from the company name
        clean_name = re.sub(r'[^a-zA-Z0-9]', '', str(company_name)).lower()
        if clean_name:
            domain = f"{clean_name}.com"
        else:
            domain = "example.com"
            
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"

def is_us_based(location):
    if not location:
        return False
    
    # Block list for international keywords
    blocked = ['australia', 'uk', 'united kingdom', 'india', 'canada', 'germany', 'france', 'europe', 'asia', 'americas']
    loc_lower = location.lower()
    
    for b in blocked:
        if b in loc_lower:
            # Special case: allow if it explicitly says "Remote (US)" or similar
            if 'remote' in loc_lower and ('us' in loc_lower or 'usa' in loc_lower):
                continue
            return False

    us_keywords = [
        'usa', 'united states', 'us', 'remote', 'san francisco', 'sf', 'new york', 'nyc',
        'austin', 'seattle', 'chicago', 'boston', 'la', 'los angeles', 'dc', 'washington dc',
        'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga', 'hi', 'id', 'il', 'in', 'ia', 'ks', 'ky', 'la', 'me', 'md', 'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv', 'nh', 'nj', 'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc', 'sd', 'tn', 'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy'
    ]
    # Check for US state codes (e.g., CA, NY, TX)
    state_codes = r'\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b'
    
    if any(kw in loc_lower for kw in us_keywords):
        return True
    if re.search(state_codes, location.upper()):
        return True
    return False

def is_direct_link(url):
    blocked_domains = [
        'linkedin.com', 'glassdoor.com', 'indeed.com', 'ziprecruiter.com', 'monster.com',
        'crunchbase.com', 'prnewswire.com', 'businesswire.com', 'facebook.com', 'twitter.com',
        'x.com', 'instagram.com', 'decrypt.co', 'alleywatch.com',
        'jobright.ai', 'simplify.jobs', 'migratemate.co', 'github.com',
        'yahoo.com',
    ]
    for domain in blocked_domains:
        if domain in url.lower():
            return False
    return True

def is_valid_apply_url(url):
    """Strict validation: URL must be a specific job application page.
    Rejects homepages, aggregators, news sites, and generic career landing pages.
    This is the FINAL gate before saving a job to the database."""
    if not url or not url.startswith('http'):
        return False

    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    netloc = parsed.netloc.lower()

    # Allow known intermediary detail pages as fallback when they are job-specific.
    if 'migratemate.co' in netloc and path and path != '/':
        return True
    # NOTE: jobright.ai URLs are NOT allowed here — they must be resolved to
    # direct ATS/company pages by the extractor. Unresolved jobright.ai links
    # will be correctly rejected by the blocked domains list below.

    # 1. Block aggregator/intermediary domains
    blocked = [
        'jobright.ai', 'simplify.jobs', 'migratemate.co', 'github.com',
        'linkedin.com', 'glassdoor.com', 'glassdoor.ca', 'indeed.com', 'ziprecruiter.com',
        'monster.com', 'facebook.com', 'twitter.com', 'x.com',
        'instagram.com', 'youtube.com', 'medium.com', 'crunchbase.com',
        'prnewswire.com', 'businesswire.com', 'yahoo.com', 'nofluffjobs.com',
        'bayt.com', 'glich.co', 'cryptojobs.com', 'nextleap.app',
        'myjobmag', 'theladders.com', 'remoteml.com', 'agenticcareers.co',
        'wellfound.com', 'themuse.com', 'builtin.com', 'ycombinator.com',
        'dice.com', 'careerbuilder.com', 'simplyhired.com', 'angel.co',
        'uaetopjobs.com', 'unatlas.org', 'nodeflair.com', 'foundit.my',
        'wizbii.com', 'apple.com/careers/hk/en/life-at-apple' # Apple life page is not a job
    ]
    if any(d in netloc for d in blocked) or netloc.endswith('.edu'):
        return False
    # Block google.com search but allow careers.google.com (Google's own ATS)
    if 'google.com' in netloc and not netloc.startswith('careers.'):
        return False

    # 2. Block news/blog sites
    news_domains = [
        'techcrunch', 'forbes', 'bloomberg', 'reuters', 'venturebeat',
        'businessinsider', 'theverge', 'wired', 'zdnet',
    ]
    if any(n in netloc for n in news_domains):
        return False
    if any(p in path for p in ['/article/', '/press/', '/blog/', '/news/', '/story/']):
        return False

    # 3. Block generic file resources
    if any(path.endswith(ext) for ext in ['.png', '.jpg', '.svg', '.gif', '.css', '.js', '.pdf']):
        return False

    # Check for specific ID patterns (numbers, UUIDs, mixed alphanumeric slugs)
    has_identifier_regex = bool(re.search(r'[0-9]{4,}|[a-f0-9]{8,}-[a-f0-9]{4}-', path.lower()))

    # 4. Block homepage-only URLs (no meaningful path)
    if not path or path == '/' or path.count('/') == 0:
        return False

    # 5. Block generic career landing pages (not job-specific)
    generic_paths = ['/careers', '/jobs', '/about', '/company', '/career', '/join', '/work', '/openings']
    if any(path.endswith(p) for p in generic_paths) and not has_identifier_regex:
        return False

    # 6. Block login and dashboard pages
    login_paths = ['/login', '/signin', '/auth', '/dashboard', '/user', '/account']
    if any(lp in path.lower() for lp in login_paths):
        return False

    # 6b. Block generic ATS portal/intro pages (career homepages, not specific job postings)
    generic_ats_pages = ['/jobs/intro', '/jobs/search', '/jobs/home', '/search/results', '/careers/home']
    if any(gap in path.lower() for gap in generic_ats_pages):
        return False

    # 6c. Block all intermediary portal domains.
    # Jobs must resolve to ATS or company domains, not intermediary listings.
    intermediary_domains = ['jobright.ai', 'migratemate.co', 'simplify.jobs']
    if any(d in netloc for d in intermediary_domains):
        return False

    # 7. STRICT ATS VALIDATION: Must have a job identifier OR be a known ATS
    # Known ATS domains that inherently represent jobs when not blocked above
    known_ats = [
        'greenhouse.io', 'lever.co', 'workday.com', 'myworkdayjobs.com',
        'ashbyhq.com', 'icims.com', 'smartrecruiters.com', 'breezy.hr',
        'bamboohr.com', 'freshteam.com', 'workable.com', 'jobvite.com'
    ]
    is_known_ats = any(ats in netloc for ats in known_ats)

    # Job-specific identifiers in the path or query
    job_identifiers = [
        '/job/', '/jobs/', '/posting/', '/viewjob', '/apply', 
        'reqid', 'requisition', 'jobid', 'job_id'
    ]
    url_lower = url.lower()
    has_identifier = any(ji in url_lower for ji in job_identifiers)

    # If it's not a known ATS and doesn't have a clear job identifier, reject
    if not is_known_ats and not has_identifier and not has_identifier_regex:
        return False

    return True

def is_live_apply_url(url, expected_company='', expected_title=''):
    """
    Active verification: Send an HTTP GET to ensure the URL is alive (200 OK)
    and does not contain text indicating the job is expired/closed.
    Uses Django caching to avoid repeated hits and BeautifulSoup to avoid false positives.
    
    FAST PATH: Known ATS direct links (greenhouse, lever, workday, ashby) are trusted
    without a live HTTP check — they are always valid job-specific pages.
    """
    from django.core.cache import cache
    import requests
    
    # ── FAST PATH: Trusted direct ATS links — skip HTTP verification ──
    # These are always specific job pages with stable URLs. No need to hit them.
    trusted_ats = [
        'boards.greenhouse.io', 'job-boards.greenhouse.io',
        'jobs.lever.co', 'hire.lever.co',
        'myworkdayjobs.com',
        'jobs.ashbyhq.com',
        'jobs.smartrecruiters.com',
        'apply.workable.com',
        'careers.icims.com',
        'app.bamboohr.com',
    ]
    url_lower = url.lower()
    if any(ats in url_lower for ats in trusted_ats):
        return True  # Trusted ATS — no HTTP check needed
    from bs4 import BeautifulSoup
    import hashlib

    # 1. Check cache first (24h TTL)
    # Include company and title in cache key so that generic redirects don't poison correct job checks
    cache_str = f"{url}_{expected_company}_{expected_title}"
    cache_key = f"live_check_{hashlib.md5(cache_str.encode()).hexdigest()}"
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        # Keep timeout short to avoid stalling a full sync pass.
        resp = requests.get(url, headers=headers, timeout=4, allow_redirects=True)
        if resp.status_code in (404, 410):
            cache.set(cache_key, False, 86400)
            return False
            
        # 3. Check for soft 404s (expired job pages that return 200)
        text = resp.text.lower()
        soft_404_phrases = [
            'job not found', 'page not found', 'no longer available', 
            'position has been closed', 'job has expired', 'this job is no longer active',
            'job is closed', '404 not found', "doesn't exist", "does not exist",
            "couldn't find that job", "link you followed is broken"
        ]
        
        # Workday specific soft-404 detection
        if 'myworkdayjobs.com' in url and "looking for doesn't exist" in text:
            cache.set(cache_key, False, 86400)
            return False

        if any(phrase in text for phrase in soft_404_phrases):
            # Potential soft-404. Let's do a false-positive check.
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Check if there is an actual application form or apply button on the page
            forms = soup.find_all('form')
            # Stricter apply button check: must contain 'apply' but NOT 'search'
            apply_buttons = soup.find_all(['a', 'button'], string=lambda s: s and 'apply' in s.lower() and 'search' not in s.lower())
            
            if not forms and not apply_buttons:
                # Confirmed soft-404
                cache.set(cache_key, False, 86400)
                return False
                
        cache.set(cache_key, True, 86400)
        return True
    except Exception:
        # Timeout or connection error — assume VALID (don't discard good jobs for network issues)
        # Only hard failures (soft-404, expired text) should cause rejection above
        cache.set(cache_key, True, 3600)  # Cache optimistically for 1h
        return True

def generate_job_hash(company, title, location, apply_url=''):
    """Generate dedup hash. Includes normalized apply URL for cross-source accuracy."""
    url_key = ''
    if apply_url:
        try:
            p = urlparse(apply_url)
            url_key = (p.netloc + p.path).lower().rstrip('/')
        except Exception:
            url_key = apply_url.lower()
    data = f"{title}|{company}|{location}|{url_key}".lower().strip()
    return hashlib.md5(data.encode()).hexdigest()

def extract_job_metadata(title, desc):
    metadata = {}
    combined = f"{title}\n{desc}".lower()

    # 1. Employment Type
    if re.search(r'\b(intern|internship|co-op)\b', combined):
        metadata['employment_type'] = 'Internship'
    elif re.search(r'\bpart[- ]time\b', combined):
        metadata['employment_type'] = 'Part-time'
    elif re.search(r'\b(contract|contractor|freelance|temp)\b', combined):
        metadata['employment_type'] = 'Contract'
    else:
        metadata['employment_type'] = 'Full-time'

    # 2. Experience Years
    exp_matches = re.finditer(r'(\d+)\s*(?:-|to)\s*(\d+)\s*\+?\s*years?(?:\s+of\s+experience)?|\b(\d+)\+?\s*years?(?:\s+of\s+experience)?', combined)
    found_years = []
    for match in exp_matches:
        if match.group(1) and match.group(2):
            found_years.append(int(match.group(1)))
            found_years.append(int(match.group(2)))
        elif match.group(3):
            found_years.append(int(match.group(3)))

    valid_years = [y for y in found_years if y < 20] # Sanity check to avoid matching years like 2026
    
    if valid_years:
        min_yr = min(valid_years)
        max_yr = max(valid_years)
        if min_yr == max_yr:
            if min_yr == 0:
                metadata['experience_years'] = 'Entry Level'
            else:
                metadata['experience_years'] = f"{min_yr}+ years"
        elif max_yr - min_yr <= 7:
            metadata['experience_years'] = f"{min_yr}-{max_yr} years"
        else:
            metadata['experience_years'] = f"{min_yr}+ years"
    else:
        if is_entry_level(title, desc):
            metadata['experience_years'] = 'Entry Level'
        else:
            metadata['experience_years'] = 'Not Specified'

    # 3. Salary Range
    salary_regexes = [
        # $100,000 to $150,000 /yr
        r'\$[\d,]+\s*(?:-|to)\s*\$[\d,]+\s*(?:/yr|/year|per year|annually)?',
        # $100k - $150k
        r'\$[\d,]+[kK]?\s*(?:-|to)\s*\$[\d,]+[kK]?',
        # $50 - $80 /hr
        r'\$[\d.]+\s*(?:-|to)\s*\$[\d.]+\s*(?:/hr|/hour|per hour|an hour|/h)'
    ]
    salary = ""
    for regex in salary_regexes:
        match = re.search(regex, desc, re.IGNORECASE)
        if match:
            salary = match.group(0).strip()
            # Clean up the format
            salary = re.sub(r'(?i)\s*(/yr|/year|per year|annually)\s*', ' /yr', salary)
            salary = re.sub(r'(?i)\s*(/hr|/hour|per hour|an hour|/h)\s*', ' /hr', salary)
            break
            
    # Try one more specifically for UK/Europe formats if no $
    if not salary:
        match = re.search(r'£[\d,]+[kK]?\s*(?:-|to)\s*£[\d,]+[kK]?', desc, re.IGNORECASE)
        if match:
            salary = match.group(0).strip()
            
    if salary:
        metadata['salary_range'] = salary
    else:
        metadata['salary_range'] = 'Not Specified'

    return metadata

def fetch_full_description(url):
    """
    Dynamically fetch the full job description from the actual job posting URL.
    This parses JSON-LD JobPosting schema natively generated by modern ATS systems 
    (Greenhouse, Workday, Lever, etc.) to get data independent of complex UI loads.
    If schema falls back, attempts heuristic HTML parsing.
    """
    try:
        # Dynamic delay so we aren't blocked when fetching hundreds of missing descriptions
        time.sleep(random.uniform(1.0, 2.5))
        resp = scraper.get(url, timeout=20)
        if resp.status_code != 200:
            return ""

        soup = BeautifulSoup(resp.text, 'html.parser')

        # 1. Look for Standard JSON-LD JobPosting Schema (Highly Reliable)
        schemas = soup.find_all('script', type='application/ld+json')
        for schema_tag in schemas:
            try:
                data = json.loads(schema_tag.string)
                # Some sites wrap multiple schemas in a list
                if isinstance(data, list):
                    for item in data:
                        if item.get('@type') == 'JobPosting' and item.get('description'):
                            return clean_text(item['description'])
                elif data.get('@type') == 'JobPosting' and data.get('description'):
                    return clean_text(data['description'])
            except:
                continue

        # 2. Heuristic HTML Extraction Fallback
        for el in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript']):
            el.decompose()

        target_classes = ['job-description', 'description', 'posting-desc', 'job-details', 'jobDetails', 'job-info', 'show-more-less-html__markup', 'app-job-description']
        target_ids = ['job-description', 'description', 'job-details', 'content']

        desc_container = None
        for class_name in target_classes:
            desc_container = soup.find(class_=re.compile(class_name, re.I))
            if desc_container: break

        if not desc_container:
            for id_name in target_ids:
                desc_container = soup.find(id=re.compile(id_name, re.I))
                if desc_container: break

        if desc_container:
            return clean_text(desc_container.get_text(separator=' ', strip=True))

        return ""
    except Exception as e:
        return ""

def get_relative_time(dt):
    """
    Returns a human-readable 'time ago' string.
    Specifically handles the client request: jobs within 24-48h show as '1 day ago'.
    """
    if not dt:
        return "—"
    
    from django.utils import timezone
    now = timezone.now()
    if dt.tzinfo is None:
        dt = timezone.make_aware(dt)
        
    diff = now - dt
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    if seconds < 172800: # Up to 48 hours (Revised from 36h)
        return "1 day ago"
    
    # Fallback to date for very old ones (though they should be archived)
    return dt.strftime('%b %d, %Y')
