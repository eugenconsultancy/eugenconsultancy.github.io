import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from .models import ConsentLog
from .models import DataRetentionRule, DataRequest
from .services import DataRetentionService, DataRequestService

logger = logging.getLogger(__name__)


@shared_task
def execute_data_retention_rules():
    """
    Celery task to execute active data retention rules.
    Runs daily to ensure GDPR compliance.
    """
    logger.info("Starting data retention rule execution")
    
    active_rules = DataRetentionRule.objects.filter(is_active=True)
    retention_service = DataRetentionService()
    
    results = []
    for rule in active_rules:
        try:
            result = retention_service.execute_rule(rule, dry_run=False)
            results.append(result)
            
            logger.info(f"Executed rule {rule.rule_name}: {result.get('processed_count', 0)} items processed")
            
        except Exception as e:
            error_result = {
                'rule_id': str(rule.id),
                'rule_name': rule.rule_name,
                'error': str(e),
                'processed_count': 0,
            }
            results.append(error_result)
            
            logger.error(f"Failed to execute rule {rule.rule_name}: {str(e)}")
    
    logger.info(f"Completed data retention execution: {len(results)} rules processed")
    return results


@shared_task
def check_overdue_data_requests():
    """
    Celery task to check for overdue data requests.
    Sends alerts for requests approaching deadlines.
    """
    logger.info("Checking for overdue data requests")
    
    now = timezone.now()
    request_service = DataRequestService()
    
    # Get requests due in the next 3 days
    warning_date = now + timezone.timedelta(days=3)
    
    upcoming_requests = DataRequest.objects.filter(
        status__in=['received', 'verifying', 'processing'],
        due_date__lte=warning_date,
        due_date__gt=now,
    ).select_related('user')
    
    # Get overdue requests
    overdue_requests = DataRequest.objects.filter(
        status__in=['received', 'verifying', 'processing'],
        due_date__lte=now,
    ).select_related('user')
    
    # Prepare notification data
    notifications = {
        'upcoming_count': upcoming_requests.count(),
        'overdue_count': overdue_requests.count(),
        'upcoming_requests': [],
        'overdue_requests': [],
    }
    
    # Format request details for notifications
    for request in upcoming_requests:
        days_remaining = (request.due_date - now).days
        notifications['upcoming_requests'].append({
            'request_id': str(request.request_id),
            'user_email': request.user.email,
            'request_type': request.get_request_type_display(),
            'days_remaining': days_remaining,
            'due_date': request.due_date.isoformat(),
        })
    
    for request in overdue_requests:
        days_overdue = (now - request.due_date).days
        notifications['overdue_requests'].append({
            'request_id': str(request.request_id),
            'user_email': request.user.email,
            'request_type': request.get_request_type_display(),
            'days_overdue': days_overdue,
            'due_date': request.due_date.isoformat(),
        })
    
    # Send notifications (in production, integrate with notification system)
    if notifications['overdue_count'] > 0 or notifications['upcoming_count'] > 0:
        logger.warning(f"Data request alerts: {notifications}")
        # Here you would send email/Slack notifications to compliance team
    
    return notifications


@shared_task
def anonymize_inactive_users():
    """
    Celery task to anonymize inactive users after retention period.
    """
    logger.info("Starting anonymization of inactive users")
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Configuration
    INACTIVITY_PERIOD_DAYS = 365 * 2  # 2 years
    retention_period = timezone.now() - timezone.timedelta(days=INACTIVITY_PERIOD_DAYS)
    
    # Find inactive users
    inactive_users = User.objects.filter(
        last_login__lt=retention_period,
        date_joined__lt=retention_period,
        is_active=True,
        data_anonymized=False,
    )
    
    retention_service = DataRetentionService()
    results = {
        'total_found': inactive_users.count(),
        'anonymized': 0,
        'errors': [],
    }
    
    for user in inactive_users:
        try:
            with transaction.atomic():
                retention_service._anonymize_user(user)
                results['anonymized'] += 1
                
                logger.info(f"Anonymized inactive user: {user.email} (ID: {user.id})")
                
        except Exception as e:
            results['errors'].append(f"User {user.id}: {str(e)}")
            logger.error(f"Failed to anonymize user {user.id}: {str(e)}")
    
    logger.info(f"Completed user anonymization: {results['anonymized']} users processed")
    return results


@shared_task
def generate_compliance_report():
    """
    Generate monthly compliance report.
    """
    logger.info("Generating monthly compliance report")
    
    from django.db.models import Count, Q
    from datetime import datetime
    
    # Get current month
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month = month_start - timezone.timedelta(days=1)
    last_month_start = last_month.replace(day=1)
    
    # Data for report
    report = {
        'period': {
            'start': last_month_start.isoformat(),
            'end': month_start.isoformat(),
            'generated_at': now.isoformat(),
        },
        'data_requests': {},
        'consent_activity': {},
        'retention_activity': {},
        'audit_summary': {},
    }
    
    # Data request statistics
    data_requests = DataRequest.objects.filter(
        received_at__gte=last_month_start,
        received_at__lt=month_start,
    )
    
    report['data_requests'] = {
        'total': data_requests.count(),
        'by_type': dict(
            data_requests.values('request_type')
            .annotate(count=Count('id'))
            .values_list('request_type', 'count')
        ),
        'by_status': dict(
            data_requests.values('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        ),
        'avg_completion_time': None,  # Would calculate average
    }
    
    # Consent activity
    consent_logs = ConsentLog.objects.filter(
        created_at__gte=last_month_start,
        created_at__lt=month_start,
    )
    
    report['consent_activity'] = {
        'total': consent_logs.count(),
        'consents_given': consent_logs.filter(consent_given=True).count(),
        'consents_withdrawn': consent_logs.filter(consent_given=False).count(),
        'by_type': dict(
            consent_logs.values('consent_type')
            .annotate(count=Count('id'))
            .values_list('consent_type', 'count')
        ),
    }
    
    # Retention rule execution
    retention_rules = DataRetentionRule.objects.filter(
        last_executed__gte=last_month_start,
        last_executed__lt=month_start,
    )
    
    report['retention_activity'] = {
        'rules_executed': retention_rules.count(),
        'total_items_processed': sum(rule.items_processed for rule in retention_rules),
        'rules': list(
            retention_rules.values('rule_name', 'data_type', 'action_type', 'items_processed')
        ),
    }
    
    # Audit summary
    from .models import AuditLog
    
    audit_logs = AuditLog.objects.filter(
        timestamp__gte=last_month_start,
        timestamp__lt=month_start,
    )
    
    report['audit_summary'] = {
        'total_logs': audit_logs.count(),
        'by_action': dict(
            audit_logs.values('action_type')
            .annotate(count=Count('id'))
            .values_list('action_type', 'count')
        ),
        'by_model': dict(
            audit_logs.values('model_name')
            .annotate(count=Count('id'))
            .values_list('model_name', 'count')
        ),
        'top_users': list(
            audit_logs.filter(user__isnull=False)
            .values('user__email')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
            .values_list('user__email', 'count')
        ),
    }
    
    # Save report to file (in production)
    logger.info(f"Compliance report generated for {last_month_start.strftime('%B %Y')}")
    
    return report