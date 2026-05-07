"""
Sociax Sync Engine — 3 Sources
Simplify Jobs | Jobright.ai | MigrateMate
"""
import os
import json
import logging
import time
import random
from datetime import datetime, timedelta, timezone as tz
from django.utils import timezone
from core.models import Job
from core.utils import (
    is_visa_sponsored,
    is_us_based, is_direct_link, generate_job_hash,
    clean_location, get_favicon_url, fetch_full_description,
    extract_job_metadata, is_valid_apply_url, is_live_apply_url
)
from core.scrapers.sources import SimplifyScraper, JobrightScraper, MigrateMateScraper, LinkResolver
from core.scrapers.categories import matches_target_titles, get_all_titles
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger('sociax_sync')


class ScraperEngine:
    def __init__(self):
        self._last_scraped = 0
        self._last_saved = 0
        self._seen_run_keys = set()
        self.jobright_stats = {'total': 0, 'internships': 0}
        self._checkpoint_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'sync_checkpoint.json'
        )
        self._live_url_cache = {}

    def run_sync(self, should_continue=None):
        """Run sync: Simplify, Jobright & MigrateMate with checkpoint resume."""
        log.info("🚀 Starting sync cycle...")

        scrapers = [
            SimplifyScraper(),
            JobrightScraper(),
            MigrateMateScraper(),
        ]

        total_scraped = 0
        total_saved = 0
        
        round_num = 1
        while True:
            # Check if we should stop
            if should_continue and not should_continue():
                log.info("🛑 Stop signal received. Ending sync.")
                break

            # ── Checkpoint Resume: per-source progress state ──
            checkpoint = self._load_checkpoint()
            source_states = checkpoint.get('source_states', {})
            completed_sources = set(checkpoint.get('completed_sources', []))
            scrapers_to_run = [s for s in scrapers if s.__class__.__name__ not in completed_sources]
            if not scrapers_to_run:
                self._save_checkpoint({'source_states': {}, 'completed_sources': []})
                scrapers_to_run = list(scrapers)
                source_states = {}
                completed_sources = set()
            log.info(f"🔄 Pass {round_num}: Fetching {len(scrapers_to_run)} sources...")
            
            pass_saved = 0
            all_raw_jobs = []
            source_results = {}
            
            # 1. Sequential fetch for deterministic progress checkpointing
            for scraper_inst in scrapers_to_run:
                name = scraper_inst.__class__.__name__
                try:
                    def _progress_update(state):
                        source_states[name] = state
                        self._save_checkpoint({
                            'pass': round_num,
                            'source_states': source_states,
                            'completed_sources': sorted(completed_sources),
                        })

                    source_jobs = scraper_inst.fetch(
                        should_continue=should_continue,
                        resume_state=source_states.get(name, {}),
                        progress_callback=_progress_update,
                    )
                    log.info(f"    📡 {name} returned {len(source_jobs)} raw listings.")
                    source_results[name] = source_jobs
                    all_raw_jobs.extend(source_jobs)
                    completed_sources.add(name)
                    self._save_checkpoint({
                        'pass': round_num,
                        'source_states': source_states,
                        'completed_sources': sorted(completed_sources),
                    })
                except Exception as e:
                    log.error(f"  🛑 {name} fetch error: {e}")

            if not all_raw_jobs:
                log.info("  ⚠️ No jobs found in this pass.")
            else:
                # 2. Filter and shuffle
                random.shuffle(all_raw_jobs)
                
                valid_jobs = [raw for raw in all_raw_jobs if self._is_job_valid(raw)]
                total_scraped += len(all_raw_jobs)
                log.info(f"    ⭐ Found {len(valid_jobs)} valid jobs after filtering.")
                print("Total keywords processed:", len(get_all_titles()))
                print("Jobs from Migratemate:", len(source_results.get('MigrateMateScraper', [])))
                print("Jobs from Simplify:", len(source_results.get('SimplifyScraper', [])))
                print("Jobs from Joblight:", len(source_results.get('JobrightScraper', [])))
                print("Total before filtering:", len(all_raw_jobs))
                print("Total after filtering:", len(valid_jobs))
                print("FINAL JOB COUNT:", len(valid_jobs))

                # 3. Parallel Link Resolution + Save
                if valid_jobs:
                    log.info(f"    🔗 Resolving + saving {len(valid_jobs)} direct links...")
                    with ThreadPoolExecutor(max_workers=20) as worker_executor:
                        futures = [worker_executor.submit(self._resolve_and_save_job, job) for job in valid_jobs]
                        for future in as_completed(futures):
                            if should_continue and not should_continue():
                                break
                            try:
                                if future.result():
                                    total_saved += 1
                                    pass_saved += 1
                            except Exception as e:
                                log.debug(f"      ❌ Resolve/Save error: {e}")

            log.info(f"  ✅ Pass {round_num} complete. +{pass_saved} jobs saved.")

            if os.getenv("SYNC_SINGLE_PASS", "0") == "1":
                log.info("  🧪 SYNC_SINGLE_PASS=1 set, stopping after one complete pass.")
                break
            
            # Reset checkpoint for next pass
            self._save_checkpoint({'source_states': {}, 'completed_sources': []})
            
            # 5-minute backoff between passes (with stop-check granularity)
            log.info("  ⏳ Next pass in 5 minutes...")
            for _ in range(300):
                if should_continue and not should_continue():
                    break
                time.sleep(1)
            
            round_num += 1

        # Final Dashboard Summary
        self._last_scraped = total_scraped
        self._last_saved = total_saved
        log.info(f"✅ Sync Session Ended: {total_scraped} processed, {total_saved} unique saved.")
        return total_scraped, total_saved

    def _is_job_valid(self, raw):
        """Check filters without resolving links yet."""
        title = (raw.get('title') or '').strip()
        location_raw = (raw.get('location') or 'USA').strip()
        location = clean_location(location_raw)
        url = (raw.get('external_apply_link') or '').strip()
        company = (raw.get('company') or 'Unknown').strip()
        source = raw.get('source', '')

        if not title or not url:
            return False
            
        # 1. Title Match
        if not matches_target_titles(title):
            log.info(f"  ❌ Title mismatch: {title}")
            return False
            
        # 2. US Based
        if not is_us_based(location):
            log.info(f"  ❌ Not US based: {location}")
            return False
            
        # 3. DATE FILTER — strict 24h across all sources
        posted_date = raw.get('posted_date')
        if not posted_date:
            log.info(f"  ❌ Missing date skip: {title}")
            return False
        
        # Ensure it's aware
        if posted_date.tzinfo is None:
            posted_date = posted_date.replace(tzinfo=tz.utc)

        time_since_posted = timezone.now() - posted_date
        
        max_age_seconds = 86400  # 24 hours
        if time_since_posted.total_seconds() > max_age_seconds:
            log.info(f"  ❌ Stale skip (>24h): {title}")
            return False

        # 4. Duplicate check by stable unique identifier (apply URL / source_job_id)
        source_job_id = str(raw.get('source_job_id', '')).strip().lower()
        unique_key = (source_job_id or url.lower())
        if not unique_key:
            return False
        if unique_key in self._seen_run_keys:
            return False
        if source_job_id and Job.objects.filter(source_job_id=source_job_id).exists():
            return False
        if not source_job_id and Job.objects.filter(external_apply_link__iexact=url).exists():
            return False
        self._seen_run_keys.add(unique_key)
            
        log.info(f"  ✅ [STRICT 24H] Valid: {title} ({source})")
        return True

    def _resolve_job_link(self, raw):
        """Worker for parallel link resolution. Returns None if intermediary can't be resolved."""
        url = raw.get('external_apply_link', '')
        intermediary_domains = ['jobright.ai', 'simplify.jobs', 'migratemate.co', 'github.com']
        is_intermediary = any(x in url for x in intermediary_domains)
        
        if is_intermediary:
            try:
                direct_link = LinkResolver.resolve_single(raw, LinkResolver.session)
                if direct_link:
                    raw['external_apply_link'] = direct_link
                else:
                    # All intermediary links MUST resolve to a direct ATS/company page.
                    # If resolution fails, drop the job entirely — never save an
                    # intermediary URL (like migratemate.co/h1b-jobs/...) that would open a generic list.
                    log.info(f"      🚫 Intermediary link unresolvable, dropping: {raw.get('company', '')[:20]}")
                    return None
            except Exception:
                log.info(f"      🚫 Resolution error, dropping: {raw.get('company', '')[:20]}")
                return None
        return raw

    def _resolve_and_save_job(self, raw):
        """Resolve intermediary links and save in one worker task."""
        resolved_job = self._resolve_job_link(raw)
        if not resolved_job:
            return False
        return self._save_job(resolved_job)

    def _save_job(self, raw):
        """Final save with strict URL validation gate."""
        title = raw.get('title', '').strip()
        company = raw.get('company', 'Unknown').strip()
        url = raw.get('external_apply_link', '')
        location = clean_location(raw.get('location', 'USA'))
        desc = raw.get('description', '')
        posted_date = raw.get('posted_date')
        
        # ══════════════════════════════════════════════════
        #  STRICT URL VALIDATION GATE — No invalid links
        # ══════════════════════════════════════════════════
        if not is_valid_apply_url(url):
            log.info(f"    🚫 Invalid apply URL rejected: {url[:60]} — {title[:30]}")
            return False
            
        # ══════════════════════════════════════════════════
        #  ACTIVE LIVE-LINK VERIFICATION & IDENTITY CHECK
        # ══════════════════════════════════════════════════
        cache_key = f"{url}|{company.lower()}|{title.lower()}"
        cached_live = self._live_url_cache.get(cache_key)
        if cached_live is None:
            cached_live = is_live_apply_url(url, expected_company=company, expected_title=title)
            self._live_url_cache[cache_key] = cached_live
        if not cached_live:
            log.warning(f"    💀 [IDENTITY/DEAD LINK] Rejected: {url[:60]} — {title[:30]} @ {company}")
            return False
        
        # Detect visa sponsorship 
        visa_type = raw.get('visa_type', '')
        if not visa_type:
            visa_type = is_visa_sponsored(title, desc) or ''

        # Resolve Logo
        logo = raw.get('company_logo')
        if not logo:
            logo = get_favicon_url(company, url)

        # Extract dynamic metadata
        meta = extract_job_metadata(title, desc)
        job_hash = generate_job_hash(company, title, location, url)

        # Attempt to fetch full description if current one is too short
        if len(desc) < 300 and is_direct_link(url):
            log.info(f"    📄 Fetching full description: {company}")
            full_desc = fetch_full_description(url)
            if full_desc and len(full_desc) > len(desc):
                desc = full_desc

        # Save once; do not overwrite existing rows.
        _, created = Job.objects.get_or_create(
            job_hash=job_hash,
            defaults={
                'source': raw.get('source', 'Unknown'),
                'source_job_id': str(raw.get('source_job_id', '')),
                'title': title,
                'company': company,
                'location': location,
                'description': desc,
                'skills': self._derive_skills(desc),
                'external_apply_link': url,
                'employment_type': raw.get('employment_type') if raw.get('employment_type') else meta.get('employment_type', 'Full-time'),
                'salary_range': raw.get('salary_range') if raw.get('salary_range') else meta.get('salary_range', ''),
                'experience_years': meta.get('experience_years', 'Not Specified'),
                'company_logo': logo,
                'posted_date': posted_date,
                'visa_type': visa_type,
            }
        )
        
        return created


    def _derive_skills(self, desc):
        if not desc:
            return ''
        skills = [
            "Python", "JavaScript", "React", "Node.js", "Java", "AWS", "SQL",
            "Django", "Next.js", "Docker", "Kubernetes", "TypeScript", "Go",
            "C++", "Ruby", "PHP", "Vue.js", "Angular", "MongoDB", "PostgreSQL",
            "Redis", "GraphQL", "REST API", "Git", "Linux", "Azure", "GCP",
            "TensorFlow", "PyTorch", "Machine Learning"
        ]
        desc_lower = desc.lower()
        found = [s for s in skills if s.lower() in desc_lower]
        return ", ".join(found)

    def _parse_date(self, date_val):
        """Parse date value. Returns None if unparseable — job will be skipped."""
        if not date_val:
            return None
        if isinstance(date_val, datetime):
            if date_val.tzinfo is None:
                date_val = timezone.make_aware(date_val)
            # If it's just a date (midnight), set to end of day to give it a 24h window
            if date_val.hour == 0 and date_val.minute == 0:
                date_val = date_val.replace(hour=23, minute=59, second=59)
            return date_val
        try:
            import dateutil.parser
            dt = dateutil.parser.parse(str(date_val))
            # If it's just a date, set to end of day
            if ' ' not in str(date_val) and ':' not in str(date_val):
                dt = dt.replace(hour=23, minute=59, second=59)
            if dt.tzinfo is None:
                return timezone.make_aware(dt)
            return dt
        except Exception:
            return None

    def remove_expired_jobs(self, days=30):
        """Archive jobs older than N days."""
        cutoff = timezone.now() - timedelta(days=days)
        expired = Job.objects.filter(posted_date__lt=cutoff, is_archived=False)
        count = expired.update(is_archived=True, is_published=False)
        if count:
            log.info(f"  🗂️ Archived {count} expired jobs.")

    def _load_checkpoint(self):
        """Load sync checkpoint from file for resume support."""
        try:
            if os.path.exists(self._checkpoint_path):
                with open(self._checkpoint_path, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {'completed_sources': [], 'source_states': {}}

    def _save_checkpoint(self, data):
        """Save sync checkpoint to file (lightweight, per-source batch only)."""
        try:
            data['updated_at'] = datetime.now(tz=tz.utc).isoformat()
            with open(self._checkpoint_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            log.debug(f"Checkpoint save error: {e}")
