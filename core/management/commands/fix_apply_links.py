"""
Management command: fix_apply_links
====================================
Re-resolves all DB jobs that still have a jobright.ai apply link,
replacing them with the actual company career page URL.

Usage:
    python manage.py fix_apply_links              # Fix all Jobright links
    python manage.py fix_apply_links --limit 20   # Fix only 20 jobs
    python manage.py fix_apply_links --dry-run    # Preview without saving
"""
from django.core.management.base import BaseCommand
from core.models import Job
from core.scrapers.jobright_extractor import JobrightURLExtractor
import time
import logging

log = logging.getLogger('sociax_sync')


class Command(BaseCommand):
    help = 'Re-resolve Jobright apply links to direct company career page URLs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Max number of jobs to fix (0 = all)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be fixed without saving'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        dry_run = options['dry_run']

        # Find all jobs that still have a jobright.ai apply link
        jobright_jobs = Job.objects.filter(
            external_apply_link__icontains='jobright.ai'
        ).order_by('-created_at')

        total = jobright_jobs.count()
        process_count = min(limit, total) if limit else total

        if limit:
            jobright_jobs = jobright_jobs[:limit]
            self.stdout.write('[INFO] Found %d Jobright jobs (processing %d)' % (total, limit))
        else:
            self.stdout.write('[INFO] Found %d Jobright jobs to fix' % total)

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN] No changes will be saved'))

        fixed = 0
        failed = 0

        for i, job in enumerate(jobright_jobs, 1):
            self.stdout.write(
                '\n[%d/%d] %s | %s' % (i, process_count, job.company[:30], job.title[:40])
            )
            self.stdout.write('  Input:  %s' % job.external_apply_link[:80])

            try:
                extractor = JobrightURLExtractor()
                result = extractor.extract(job.external_apply_link)

                if result.get('status') == 'success':
                    new_url = result['final_url']
                    self.stdout.write(
                        self.style.SUCCESS('  [OK]   -> %s' % new_url[:80])
                    )
                    self.stdout.write(
                        '         via %s (%.1fs conf=%.2f)' % (
                            result['method'], result['time_taken'], result['confidence']
                        )
                    )
                    if not dry_run:
                        job.external_apply_link = new_url
                        job.save(update_fields=['external_apply_link'])
                    fixed += 1
                else:
                    self.stdout.write(
                        self.style.WARNING('  [FAIL] %s' % result.get('reason', 'unknown'))
                    )
                    failed += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR('  [ERROR] %s' % str(e)))
                failed += 1

            # Small delay to avoid hammering servers
            time.sleep(0.3)

        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(
            'DONE: Fixed=%d  Failed=%d  Total=%d' % (fixed, failed, process_count)
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING('(Dry run -- no changes were saved to DB)'))
        self.stdout.write('=' * 60)
