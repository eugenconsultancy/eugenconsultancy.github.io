# apps/notifications/tasks.py
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

from apps.notifications.models import Notification, NotificationLog
from apps.notifications.services import EmailService, PushNotificationService

logger = logging.getLogger(__name__)


@shared_task
def deliver_notification(notification_id: str):
    """
    Deliver a notification through all enabled channels.
    """
    try:
        notification = Notification.objects.get(id=notification_id)
        
        # Skip if already sent
        if notification.is_sent:
            return
        
        # Mark as being processed
        notification.record_attempt()
        
        # Get user preferences
        from apps.notifications.models import NotificationPreference
        try:
            pref = NotificationPreference.objects.get(user=notification.user)
        except NotificationPreference.DoesNotExist:
            pref = NotificationPreference.objects.create(user=notification.user)
        
        # Check if we should deliver now
        if notification.scheduled_for and notification.scheduled_for > timezone.now():
            # Reschedule for later
            deliver_notification.apply_async(
                args=[notification_id],
                eta=notification.scheduled_for
            )
            return
        
        # Deliver through channels
        channels = notification.channels
        if channels == 'all':
            channels_to_deliver = ['email', 'push', 'in_app']
        else:
            channels_to_deliver = [channels]
        
        success = True
        
        for channel in channels_to_deliver:
            if not pref.is_category_enabled('system', channel):
                continue
            
            if channel == 'email':
                # Send email
                email_sent = EmailService.send_templated_email(
                    recipient_email=notification.user.email,
                    template_name='system_notification',
                    context={
                        'user_name': notification.user.get_full_name() or notification.user.email,
                        'notification_title': notification.title,
                        'notification_message': notification.message,
                        'action_url': notification.action_url,
                        'action_text': notification.action_text,
                        **notification.context_data
                    },
                    recipient_user=notification.user,
                    priority=notification.priority
                )
                
                if not email_sent:
                    success = False
                    
            elif channel == 'push':
                # Send push notification
                push_sent = PushNotificationService.send_push_notification(
                    user=notification.user,
                    title=notification.title,
                    body=notification.message,
                    data=notification.context_data
                )
                
                if not push_sent:
                    success = False
            
            elif channel == 'in_app':
                # In-app notification is already created
                pass
        
        if success:
            notification.mark_as_sent()
            logger.info(f"Notification {notification_id} delivered successfully")
        else:
            logger.warning(f"Notification {notification_id} partially delivered")
        
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
    except Exception as e:
        logger.error(f"Error delivering notification {notification_id}: {e}")


@shared_task
def deliver_scheduled_notification(notification_id: str):
    """
    Deliver a scheduled notification.
    """
    deliver_notification.delay(notification_id)


@shared_task
def send_daily_digest():
    """
    Send daily digest emails to users.
    """
    from django.db.models import Count
    from apps.accounts.models import User
    
    # Get users who want daily digest
    users = User.objects.filter(
        notification_preferences__preferences__daily_digest=True
    )
    
    for user in users:
        try:
            # Get today's notifications
            today = timezone.now().date()
            start_of_day = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
            
            notifications = Notification.objects.filter(
                user=user,
                created_at__gte=start_of_day,
                notification_type__in=['info', 'success', 'warning']
            ).order_by('-created_at')[:10]
            
            if notifications.exists():
                # Prepare digest content
                notification_items = []
                for notif in notifications:
                    notification_items.append({
                        'title': notif.title,
                        'message': notif.message[:100] + ('...' if len(notif.message) > 100 else ''),
                        'type': notif.notification_type,
                        'time': notif.created_at.strftime('%H:%M'),
                        'url': notif.action_url
                    })
                
                # Send digest email
                EmailService.send_templated_email(
                    recipient_email=user.email,
                    template_name='daily_digest',
                    context={
                        'user_name': user.get_full_name() or user.email,
                        'notification_count': notifications.count(),
                        'notifications': notification_items,
                        'date': today.strftime('%B %d, %Y'),
                    },
                    recipient_user=user,
                    priority=1  # Low priority for digests
                )
                
                logger.info(f"Daily digest sent to {user.email}")
                
        except Exception as e:
            logger.error(f"Error sending daily digest to {user.email}: {e}")

@shared_task
def send_verification_notification(user_id: int, status: str):
    """
    Wrapper task to create and deliver verification updates.
    """
    from apps.notifications.models import Notification # Local import to avoid circularity
    
    # Logic to create the notification record
    notification = Notification.objects.create(
        user_id=user_id,
        title="Verification Update",
        message=f"Your verification status has been updated to: {status}",
        notification_type='VERIFICATION'
    )
    
    # Call your existing delivery logic
    return deliver_notification(notification.id)


@shared_task
def send_order_notification(user_id, order_id, notification_type, message_context=None):
    """
    Task to create and send notifications related to order assignments.
    """
    try:
        User = get_user_model()
        user = User.objects.get(id=user_id)
        
        # Import models locally to avoid circular imports
        from apps.notifications.models import Notification
        
        # Create the notification record
        notification = Notification.objects.create(
            user=user,
            title=f"Order Update: {order_id}",
            message=message_context or f"There is an update regarding order #{order_id}",
            notification_type=notification_type
        )
        
        # Trigger your existing delivery logic
        # Assuming deliver_notification is already defined in this file
        from .tasks import deliver_notification
        deliver_notification.delay(notification.id)
        
        return f"Order notification queued for user {user_id}"
    except Exception as e:
        logger.error(f"Error sending order notification: {str(e)}")
        return False
    

@shared_task
def cleanup_old_notifications(days=90):
    """
    Clean up old notifications.
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    try:
        # Delete old notifications
        deleted_count, _ = Notification.objects.filter(
            created_at__lt=cutoff_date,
            is_sent=True,
            is_read=True
        ).delete()
        
        # Delete old logs
        log_deleted_count, _ = NotificationLog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleaned up {deleted_count} old notifications and {log_deleted_count} logs")
        
    except Exception as e:
        logger.error(f"Error cleaning up old notifications: {e}")


@shared_task
def retry_failed_notifications(hours=1):
    """
    Retry failed notifications from the last hour.
    """
    retry_cutoff = timezone.now() - timedelta(hours=hours)
    
    try:
        failed_notifications = Notification.objects.filter(
            is_sent=False,
            send_attempts__lt=3,
            last_attempt_at__lt=retry_cutoff
        )
        
        for notification in failed_notifications:
            deliver_notification.delay(str(notification.id))
        
        logger.info(f"Retrying {failed_notifications.count()} failed notifications")
        
    except Exception as e:
        logger.error(f"Error retrying failed notifications: {e}")