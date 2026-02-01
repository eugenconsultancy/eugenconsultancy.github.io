"""
Celery configuration for EBWriting platform.
"""
import os
from celery import Celery
from celery.schedules import crontab
from datetime import timedelta
from django.conf import settings
# config/celery.py

from django.utils import timezone

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('ebwriting')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Configure Celery beat schedule with all phases
app.conf.beat_schedule = {
    # Phase 1 - Foundation & Compliance Tasks
    'cleanup-expired-sessions': {
        'task': 'apps.compliance.tasks.cleanup_expired_sessions',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    'process-data-requests': {
        'task': 'apps.compliance.tasks.process_pending_data_requests',
        'schedule': timedelta(minutes=30),  # Every 30 minutes
    },
    'anonymize-old-data': {
        'task': 'apps.compliance.tasks.anonymize_old_data',
        'schedule': crontab(hour=4, minute=0, day_of_week='sunday'),  # Weekly Sunday at 4 AM
    },
    
    # Phase 2 - Communication & Delivery Tasks
    'send-daily-digest': {
        'task': 'apps.notifications.tasks.send_daily_digest',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    'cleanup-old-notifications': {
        'task': 'apps.notifications.tasks.cleanup_old_notifications',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        'args': (90,),  # Keep 90 days of notifications
    },
    'retry-failed-notifications': {
        'task': 'apps.notifications.tasks.retry_failed_notifications',
        'schedule': timedelta(minutes=15),  # Every 15 minutes
    },
    'scan-pending-attachments': {
        'task': 'apps.messaging.tasks.scan_pending_attachments',
        'schedule': timedelta(minutes=30),  # Every 30 minutes
    },
    'cleanup-old-attachments': {
        'task': 'apps.messaging.tasks.cleanup_old_attachments',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
        'args': (90,),  # Keep 90 days of attachments
    },
    'send-deadline-reminders': {
        'task': 'apps.notifications.tasks.send_deadline_reminders',
        'schedule': timedelta(minutes=30),  # Every 30 minutes
    },
    'generate-scheduled-documents': {
        'task': 'apps.documents.tasks.generate_scheduled_documents',
        'schedule': crontab(hour=0, minute=30),  # Daily at 12:30 AM
    },
    
    # Phase 3 - Quality, Disputes & API Tasks
    'check-overdue-revisions': {
        'task': 'apps.revisions.services.RevisionService.check_overdue_revisions',
        'schedule': timedelta(minutes=30),  # Every 30 minutes
    },
    'monitor-pending-plagiarism-checks': {
        'task': 'apps.plagiarism.tasks.monitor_pending_checks',
        'schedule': timedelta(minutes=15),  # Every 15 minutes
    },
    'cleanup-expired-plagiarism-reports': {
        'task': 'apps.plagiarism.tasks.cleanup_expired_reports',
        'schedule': crontab(hour=3, minute=30),  # Daily at 3:30 AM
    },
    'check-dispute-sla': {
        'task': 'apps.disputes.services.DisputeService.check_sla_breaches',
        'schedule': timedelta(minutes=30),  # Every 30 minutes
    },
    'escalate-overdue-disputes': {
        'task': 'apps.disputes.tasks.escalate_overdue_disputes',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'cleanup-api-tokens': {
        'task': 'apps.api.tasks.cleanup_expired_tokens',
        'schedule': crontab(hour=5, minute=0),  # Daily at 5 AM
    },
    
    # Phase 4 - Writer Economy & Analytics Tasks
    # Analytics Tasks
    'calculate-daily-kpis': {
        'task': 'apps.analytics.tasks.calculate_all_kpis_task',
        'schedule': crontab(hour=0, minute=5),  # Daily at 12:05 AM
    },
    'process-scheduled-reports': {
        'task': 'apps.analytics.tasks.process_scheduled_reports',
        'schedule': crontab(hour=1, minute=0),  # Daily at 1 AM
    },
    'cleanup-old-reports': {
        'task': 'apps.analytics.tasks.cleanup_old_reports',
        'schedule': crontab(hour=2, minute=0, day_of_week='sunday'),  # Weekly on Sunday at 2 AM
        'args': (30,),  # Cleanup reports older than 30 days
    },
    'send-kpi-alerts': {
        'task': 'apps.analytics.tasks.send_kpi_alerts',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
    },
    'generate-periodic-reports': {
        'task': 'apps.analytics.tasks.generate_periodic_reports',
        'schedule': crontab(hour=0, minute=0, day_of_month='1'),  # Monthly on 1st at midnight
    },
    
    # Reviews Tasks
    'process-review-flags': {
        'task': 'apps.reviews.moderation.ReviewModerationService.process_flags',
        'schedule': timedelta(hours=6),  # Every 6 hours
    },
    'update-writer-ratings': {
        'task': 'apps.reviews.tasks.update_all_writer_ratings',
        'schedule': crontab(hour=2, minute=30),  # Daily at 2:30 AM
    },
    'send-review-reminders': {
        'task': 'apps.reviews.tasks.send_review_reminders',
        'schedule': crontab(hour=10, minute=0),  # Daily at 10 AM
    },
    'cleanup-old-review-flags': {
        'task': 'apps.reviews.tasks.cleanup_old_flags',
        'schedule': crontab(hour=3, minute=0, day_of_week='monday'),  # Weekly Monday at 3 AM
    },
    
    # Wallet Tasks
    'process-pending-payouts': {
        'task': 'apps.wallet.tasks.process_pending_payouts',
        'schedule': crontab(hour=11, minute=0),  # Daily at 11 AM
    },
    'reconcile-wallet-transactions': {
        'task': 'apps.wallet.tasks.reconcile_transactions',
        'schedule': crontab(hour=4, minute=0),  # Daily at 4 AM
    },
    'send-payout-reminders': {
        'task': 'apps.wallet.tasks.send_payout_reminders',
        'schedule': crontab(hour=14, minute=0),  # Daily at 2 PM
    },
    'calculate-writer-commissions': {
        'task': 'apps.wallet.tasks.calculate_writer_commissions',
        'schedule': crontab(hour=0, minute=30),  # Daily at 12:30 AM
    },
    
    # System Maintenance Tasks
    'cleanup-temp-files': {
        'task': 'apps.compliance.tasks.cleanup_temp_files',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
    },
    'update-search-index': {
        'task': 'apps.analytics.tasks.update_search_index',
        'schedule': crontab(hour=5, minute=30),  # Daily at 5:30 AM
    },
    'backup-database': {
        'task': 'apps.compliance.tasks.backup_database',
        'schedule': crontab(hour=23, minute=0),  # Daily at 11 PM
    },
}

# Timezone configuration
app.conf.timezone = 'UTC'
app.conf.enable_utc = True

# Task routing configuration
app.conf.task_routes = {
    'apps.analytics.tasks.*': {'queue': 'analytics'},
    'apps.reviews.tasks.*': {'queue': 'reviews'},
    'apps.wallet.tasks.*': {'queue': 'wallet'},
    'apps.notifications.tasks.*': {'queue': 'notifications'},
    'apps.messaging.tasks.*': {'queue': 'messaging'},
    'apps.compliance.tasks.*': {'queue': 'compliance'},
    'apps.plagiarism.tasks.*': {'queue': 'plagiarism'},
    'apps.revisions.tasks.*': {'queue': 'revisions'},
    'apps.disputes.tasks.*': {'queue': 'disputes'},
    'apps.api.tasks.*': {'queue': 'api'},
}

# Task result configuration
app.conf.result_backend = 'django-db'
app.conf.result_expires = timedelta(days=7)
app.conf.result_persistent = True

# Task execution configuration
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True
app.conf.task_track_started = True
app.conf.worker_prefetch_multiplier = 1
app.conf.worker_max_tasks_per_child = 1000

# Retry configuration
app.conf.task_default_retry_delay = 30  # 30 seconds
app.conf.task_max_retries = 3

# Security configuration
app.conf.worker_disable_rate_limits = True
app.conf.broker_connection_retry_on_startup = True

# Monitoring configuration
app.conf.worker_send_task_events = True
app.conf.task_send_sent_event = True


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')
    return {'status': 'ok', 'task_id': self.request.id}


# Error handling middleware
@app.task(bind=True)
def error_handler(self, uuid):
    """Log task errors"""
    result = self.app.AsyncResult(uuid)
    exc = result.result
    if isinstance(exc, Exception):
        print(f'Task {uuid} raised exception: {exc!r}')


# Task tracking
@app.task(bind=True)
def track_task_progress(self, current, total):
    """Update task progress"""
    self.update_state(
        state='PROGRESS',
        meta={'current': current, 'total': total, 'percent': int((current / total) * 100)}
    )


# Health check task
@app.task
def health_check():
    """Health check task for monitoring"""
    return {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0'
    }


# Add missing task modules discovery
def autodiscover_tasks():
    """Auto-discover task modules in all installed apps"""
    from django.apps import apps
    for app_config in apps.get_app_configs():
        try:
            __import__(f'{app_config.name}.tasks')
        except ImportError:
            continue


# Initialize task discovery
autodiscover_tasks()

# Configure periodic health checks
app.conf.beat_schedule.update({
    'health-check': {
        'task': 'config.celery.health_check',
        'schedule': timedelta(minutes=5),
    },
})