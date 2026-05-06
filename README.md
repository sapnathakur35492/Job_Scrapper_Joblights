# Sociax Job Scraper

Dynamic multi-source job scraper for:
- `Simplify`
- `Joblight` (Jobright)
- `Migratemate`

The engine enforces:
- exact `98` keyword set (from `core/scrapers/categories.py`)
- last `24 hours` filtering with timezone-aware datetimes
- URL/job-id based dedupe
- checkpoint resume without restarting full source scans

## Setup

```bash
pip install -r requirements.txt
python manage.py migrate
```

Optional `.env` values:
- `SYNC_INTERVAL_MINS` (default `5`)
- `DEBUG` (`True`/`False`)
- `ALLOWED_HOSTS`

## Run

Dashboard:
```bash
python manage.py runserver
```

Background sync command:
```bash
python manage.py run_sync
```

One-pass verification mode:
```bash
SYNC_SINGLE_PASS=1 python manage.py run_sync
```

## Resume Behavior

Checkpoint file: `sync_checkpoint.json`

The engine persists progress for each source:
- Simplify: completed repos
- Joblight: completed repos
- Migratemate: category index + next page

If interrupted, restart normally. The next run resumes from checkpoint state and continues from the last saved source/page, then clears checkpoint state after a complete pass.

## Data Rules

- No hardcoded result caps.
- No fixed page limits.
- Duplicate prevention uses:
  - `external_apply_link` (primary)
  - `source_job_id` (secondary)
- Existing rows are not overwritten.

## Export

```bash
python manage.py export_jobs
```
