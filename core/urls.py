from django.urls import path
from core import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('jobs/', views.job_list, name='job_list'),
    path('jobs/<int:job_id>/', views.job_detail, name='job_detail'),
    path('export/', views.export_csv, name='export_csv'),
    path('jobs/<int:job_id>/delete/', views.delete_job, name='delete_job'),
    path('api/clear-all/', views.clear_all_jobs, name='clear_all_jobs'),
    path('api/trigger-sync/', views.api_trigger_sync, name='api_trigger_sync'),
    path('api/stop-sync/', views.api_stop_sync, name='api_stop_sync'),
    path('api/status/', views.api_status, name='api_status'),
    path('api/extract-url/', views.api_extract_url, name='api_extract_url'),
    path('extract/', views.extract_url_page, name='extract_url'),
]
