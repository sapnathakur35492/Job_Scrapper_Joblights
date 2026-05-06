import csv
import json
import threading
from datetime import timedelta

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import Job
from core.utils import get_relative_time

# ── Global sync state ──
_sync_state = {
    'running': False,
    'start_time': None,
    'last_sync': None,
    'last_scraped': 0,
    'last_saved': 0,
}


def dashboard(request):
    """Main dashboard with stats, source health, and recent jobs."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_jobs = Job.objects.count()
    published_jobs = Job.objects.filter(is_published=True).count()
    reviewing_jobs = Job.objects.filter(is_reviewing=True).count()
    archived_jobs = Job.objects.filter(is_archived=True).count()
    visa_jobs = Job.objects.exclude(visa_type='').exclude(visa_type__isnull=True).count()
    today_jobs = Job.objects.filter(created_at__gte=today_start).count()

    # Source breakdown
    raw_sources = (
        Job.objects.values('source')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    source_counts = {}
    for rs in raw_sources:
        s_name = rs['source'] or 'Unknown'
        if 'Jobright' in s_name:
            base_name = 'Jobright'
        elif 'Simplify' in s_name:
            base_name = 'Simplify'
        elif 'MigrateMate' in s_name:
            base_name = 'MigrateMate'
        else:
            base_name = s_name.split('/')[0]
            
        source_counts[base_name] = source_counts.get(base_name, 0) + rs['count']
        
    sources = [{'source': k, 'count': v} for k, v in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)]

    # Recent jobs
    recent_jobs = Job.objects.order_by('-created_at')[:15]
    for j in recent_jobs:
        j.posted_date_relative = get_relative_time(j.posted_date)

    context = {
        'total_jobs': total_jobs,
        'published_jobs': published_jobs,
        'reviewing_jobs': reviewing_jobs,
        'archived_jobs': archived_jobs,
        'visa_jobs': visa_jobs,
        'today_jobs': today_jobs,
        'sources': sources,
        'recent_jobs': recent_jobs,
        'sync_running': _sync_state['running'],
        'last_sync': _sync_state['last_sync'],
    }
    return render(request, 'core/dashboard.html', context)


def job_list(request):
    """Searchable, filterable, paginated job listing."""
    jobs = Job.objects.all().order_by('-created_at')

    # Search
    search_query = request.GET.get('q', '').strip()
    if search_query:
        jobs = jobs.filter(
            Q(title__icontains=search_query) |
            Q(company__icontains=search_query) |
            Q(skills__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Filter by source
    source_filter = request.GET.get('source', '')
    if source_filter:
        jobs = jobs.filter(source__istartswith=source_filter)

    # Filter by visa type
    visa_filter = request.GET.get('visa', '')
    if visa_filter:
        jobs = jobs.filter(visa_type__icontains=visa_filter)

    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter == 'published':
        jobs = jobs.filter(is_published=True)
    elif status_filter == 'reviewing':
        jobs = jobs.filter(is_reviewing=True)
    elif status_filter == 'archived':
        jobs = jobs.filter(is_archived=True)

    # Available sources for filter dropdown
    available_sources = ['Jobright', 'MigrateMate', 'Simplify']

    paginator = Paginator(jobs, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Add relative time for display
    for job in page_obj:
        job.posted_date_relative = get_relative_time(job.posted_date)

    context = {
        'jobs': page_obj,
        'search_query': search_query,
        'source_filter': source_filter,
        'visa_filter': visa_filter,
        'status_filter': status_filter,
        'available_sources': available_sources,
        'sync_running': _sync_state['running'],
    }
    return render(request, 'core/job_list.html', context)


def job_detail(request, job_id):
    """Single job detail page."""
    job = get_object_or_404(Job, id=job_id)
    skills_list = [s.strip() for s in job.skills.split(',') if s.strip()] if job.skills else []
    
    # Add relative time for display
    job.posted_date_relative = get_relative_time(job.posted_date)

    context = {
        'job': job,
        'skills_list': skills_list,
        'sync_running': _sync_state['running'],
    }
    return render(request, 'core/job_detail.html', context)


@csrf_exempt
@require_POST
def api_trigger_sync(request):
    """API endpoint to trigger a continuous sync."""
    global _sync_state

    if _sync_state['running']:
        return JsonResponse({'status': 'busy', 'message': 'Sync already running'})

    def run_sync_task():
        global _sync_state
        _sync_state['running'] = True
        _sync_state['start_time'] = timezone.now().isoformat()
        _sync_state['last_scraped'] = 0
        _sync_state['last_saved'] = 0
        
        def should_continue():
            return _sync_state['running']

        try:
            from core.scrapers.engine import ScraperEngine
            engine = ScraperEngine()
            engine.run_sync(should_continue=should_continue)
            
            _sync_state['last_scraped'] = getattr(engine, '_last_scraped', 0)
            _sync_state['last_saved'] = getattr(engine, '_last_saved', 0)
        except Exception as e:
            print(f"Sync error: {e}")
        finally:
            _sync_state['running'] = False
            _sync_state['last_sync'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')

    thread = threading.Thread(target=run_sync_task, daemon=True)
    thread.start()

    return JsonResponse({
        'status': 'ok',
        'message': 'Continuous sync started',
    })


@csrf_exempt
@require_POST
def api_stop_sync(request):
    """API endpoint to stop the continuous sync."""
    global _sync_state
    if _sync_state['running']:
        _sync_state['running'] = False
        return JsonResponse({'status': 'ok', 'message': 'Stop signal sent'})
    return JsonResponse({'status': 'ok', 'message': 'Not running'})


def api_status(request):
    """Enriched API endpoint for sync status and real-time dashboard updates."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    recent_jobs_query = Job.objects.order_by('-created_at')[:15]
    recent_jobs = []
    for j in recent_jobs_query:
        recent_jobs.append({
            'id': j.id,
            'title': j.title,
            'company': j.company,
            'company_logo': j.company_logo,
            'location': j.location,
            'source': j.source,
            'visa_type': j.visa_type,
            'posted_date': get_relative_time(j.posted_date),
            'external_apply_link': j.external_apply_link,
            'url': f"/jobs/{j.id}/"
        })

    return JsonResponse({
        'syncing': _sync_state['running'],
        'start_time': _sync_state['start_time'],
        'last_sync': _sync_state['last_sync'],
        'total_jobs': Job.objects.count(),
        'published_jobs': Job.objects.filter(is_published=True).count(),
        'reviewing_jobs': Job.objects.filter(is_reviewing=True).count(),
        'visa_jobs': Job.objects.exclude(visa_type='').exclude(visa_type__isnull=True).count(),
        'today_jobs': Job.objects.filter(created_at__gte=today_start).count(),
        'archived_jobs': Job.objects.filter(is_archived=True).count(),
        'recent_jobs': recent_jobs,
    })


def export_csv(request):
    """Export all jobs as CSV in the exact required format."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sociax_jobs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Job Title',
        'Company Name',
        'Company Logo URL',
        'Location',
        'Employment Type',
        'Experience',
        'Posted / Updated Date',
        'Salary',
        'Required Skills',
        'Full Job Description',
        'Direct Company Apply URL'
    ])

    jobs = Job.objects.all().order_by('-created_at')
    for job in jobs:
        posted_date = job.posted_date.strftime('%Y-%m-%d') if job.posted_date else ''
        writer.writerow([
            job.title,
            job.company,
            job.company_logo,
            job.location,
            job.employment_type,
            job.experience_years,
            posted_date,
            job.salary_range,
            job.skills,
            job.description,
            job.external_apply_link,
        ])

    return response


@csrf_exempt
@require_POST
def delete_job(request, job_id):
    """Delete a single job by ID."""
    job = get_object_or_404(Job, id=job_id)
    job.delete()
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_POST
def clear_all_jobs(request):
    """Delete all jobs from the database (All Clear)."""
    Job.objects.all().delete()
    return JsonResponse({'status': 'ok'})


def extract_url_page(request):
    """Standalone URL extractor page."""
    # Note: _sync_state is globally defined in this file.
    return render(request, 'core/extract_url.html', {
        'sync_running': _sync_state.get('running', False),
    })


@csrf_exempt
@require_POST
def api_extract_url(request):
    """
    API endpoint for extracting final job URLs from Jobright apply links.
    Supports single URL or batch mode.
    
    Single: {"url": "https://jobright.ai/jobs/info/..."}
    Batch:  {"urls": ["...", "..."]}
    """
    import logging
    log = logging.getLogger('sociax_sync.extractor')

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'reason': 'Invalid JSON body'}, status=400)

    from core.scrapers.jobright_extractor import extract_jobright_url, extract_jobright_urls_batch

    # Batch mode
    urls = body.get('urls')
    if urls and isinstance(urls, list):
        if len(urls) > 20:
            return JsonResponse({'status': 'error', 'reason': 'Max 20 URLs per batch'}, status=400)
        log.info(f"📦 Batch extraction: {len(urls)} URLs")
        results = extract_jobright_urls_batch(urls)
        return JsonResponse({'results': results})

    # Single mode
    url = body.get('url', '').strip()
    if not url:
        return JsonResponse({'status': 'error', 'reason': 'Missing "url" or "urls" field'}, status=400)

    log.info(f"🔍 Single extraction: {url}")
    result = extract_jobright_url(url)
    return JsonResponse(result)
