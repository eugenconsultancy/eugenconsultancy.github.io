"""
Celery tasks for plagiarism detection.
"""
from celery import shared_task
import logging
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from .services import PlagiarismService
from .models import PlagiarismCheck, PlagiarismReport

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_plagiarism_check(self, check_id):
    """
    Process a plagiarism check asynchronously.
    
    Args:
        check_id: PlagiarismCheck ID as string
    """
    try:
        logger.info(f"Starting plagiarism check processing: {check_id}")
        result = PlagiarismService.process_plagiarism_check(check_id)
        logger.info(f"Completed plagiarism check: {check_id}")
        return str(result.id)
    except Exception as exc:
        logger.error(f"Failed to process plagiarism check {check_id}: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task
def cleanup_expired_reports():
    """
    Clean up expired plagiarism reports.
    Runs daily to remove reports older than retention period.
    """
    try:
        retention_days = getattr(settings, 'PLAGIARISM_REPORT_RETENTION_DAYS', 365)
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        # Get expired reports
        expired_reports = PlagiarismReport.objects.filter(
            expires_at__lt=cutoff_date
        )
        
        count = expired_reports.count()
        expired_reports.delete()
        
        logger.info(f"Cleaned up {count} expired plagiarism reports")
        return count
        
    except Exception as e:
        logger.error(f"Error cleaning up expired reports: {str(e)}")
        return 0


@shared_task
def monitor_pending_checks():
    """
    Monitor and retry failed plagiarism checks.
    Runs hourly to ensure all checks are processed.
    """
    try:
        # Find pending checks older than 1 hour
        one_hour_ago = timezone.now() - timedelta(hours=1)
        pending_checks = PlagiarismCheck.objects.filter(
            status='pending',
            requested_at__lt=one_hour_ago
        )
        
        # Find failed checks from last 24 hours
        one_day_ago = timezone.now() - timedelta(days=1)
        failed_checks = PlagiarismCheck.objects.filter(
            status='failed',
            requested_at__gt=one_day_ago
        )
        
        total_retried = 0
        
        # Retry pending checks
        for check in pending_checks:
            try:
                process_plagiarism_check.delay(str(check.id))
                total_retried += 1
            except Exception as e:
                logger.error(f"Failed to retry pending check {check.id}: {str(e)}")
        
        # Retry failed checks
        for check in failed_checks:
            try:
                check.status = 'pending'
                check.save()
                process_plagiarism_check.delay(str(check.id))
                total_retried += 1
            except Exception as e:
                logger.error(f"Failed to retry failed check {check.id}: {str(e)}")
        
        logger.info(f"Retried {total_retried} plagiarism checks")
        return total_retried
        
    except Exception as e:
        logger.error(f"Error monitoring plagiarism checks: {str(e)}")
        return 0