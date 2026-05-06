import time
from django.core.management.base import BaseCommand
from core.scrapers.engine import ScraperEngine
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
import os

load_dotenv()

class Command(BaseCommand):
    help = 'Runs the job sync engine every 5-10 minutes.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting Sociax Auto-Sync Engine...'))
        
        engine = ScraperEngine()
        query = os.getenv("JOB_QUERY", "software engineer")
        interval = int(os.getenv("SYNC_INTERVAL_MINS", 5))

        scheduler = BlockingScheduler()

        def sync_task():
            self.stdout.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Triggering sync...")
            engine.run_sync()

        # Run immediately on start
        sync_task()

        # Schedule subsequent runs
        scheduler.add_job(sync_task, 'interval', minutes=interval)
        
        try:
            self.stdout.write(self.style.SUCCESS(f"Scheduler started. Syncing every {interval} minutes."))
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write(self.style.WARNING("Sync engine stopped."))
