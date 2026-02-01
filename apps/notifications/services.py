# apps/notifications/services.py
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.template.loader import render_to_string
from django.db import models
from django.core.mail import EmailMultiAlternatives
from apps.notifications.websocket_utils import WebSocketNotificationService

from apps.notifications.models import (
    Notification, NotificationPreference, EmailTemplate, NotificationLog
)
from apps.messaging.models import Message

logger = logging.getLogger(__name__)


# Update the NotificationService class methods to include WebSocket notifications
class NotificationService:
    """Main service for handling notifications (updated with WebSocket support)"""
    
    @staticmethod
    @transaction.atomic
    def create_notification(
        user,
        title: str,
        message: str,
        notification_type: str = 'info',
        channels: str = 'in_app',
        priority: int = 2,
        context_data: Optional[Dict] = None,
        action_url: Optional[str] = None,
        action_text: Optional[str] = None,
        scheduled_for: Optional[datetime] = None
    ) -> Notification:
        """
        Create a new notification with WebSocket support.
        """
        # Get or create notification preferences
        pref, _ = NotificationPreference.objects.get_or_create(user=user)
        
        # Check if user is in quiet hours
        if pref.in_quiet_hours() and priority < 3:  # Don't send low/medium priority in quiet hours
            channels = 'in_app'  # Only send in-app during quiet hours
        
        # Create notification
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            channels=channels,
            priority=priority,
            context_data=context_data or {},
            action_url=action_url,
            action_text=action_text,
            scheduled_for=scheduled_for
        )
        
        # Schedule delivery
        if scheduled_for:
            from apps.notifications.tasks import deliver_scheduled_notification
            deliver_scheduled_notification.apply_async(
                args=[str(notification.id)],
                eta=scheduled_for
            )
        else:
            from apps.notifications.tasks import deliver_notification
            deliver_notification.delay(str(notification.id))
        
        logger.info(f"Notification created for {user.email}: {title}")
        
        # After creating notification, send via WebSocket if push channel is enabled
        if 'push' in channels or channels == 'all':
            try:
                # Get unread count for user
                unread_count = NotificationService.get_unread_count(user)
                
                # Prepare WebSocket notification data
                ws_data = {
                    'id': str(notification.id),  # Use the created notification object
                    'title': title,
                    'message': message,
                    'category': 'system',  # Default category
                    'notification_type': notification_type,
                    'priority': priority,
                    'action_url': action_url,
                    'action_text': action_text,
                    'context_data': context_data or {},
                    'timestamp': notification.created_at.isoformat(),
                    'unread_count': unread_count + 1  # Include new notification
                }
                
                # Determine category from context or notification type
                if context_data and 'category' in context_data:
                    ws_data['category'] = context_data['category']
                elif notification_type == 'order_update':
                    ws_data['category'] = 'order_updates'
                elif notification_type == 'message':
                    ws_data['category'] = 'messages'
                elif notification_type == 'payment':
                    ws_data['category'] = 'payments'
                
                # Send via WebSocket
                from apps.notifications.websocket_utils import WebSocketNotificationService
                WebSocketNotificationService.send_notification_to_user(
                    user_id=str(user.id),
                    notification_data=ws_data
                )
                
            except Exception as e:
                logger.error(f"Error sending WebSocket notification: {e}")
        
        return notification  # Return the created notification object
    
    @staticmethod
    def create_message_notification(user, message: Message, sender) -> Notification:
        """
        Create notification for new message.
        
        Args:
            user: Recipient user
            message: The message
            sender: Message sender
        
        Returns:
            Created Notification instance
        """
        title = "New Message"
        notification_message = f"You have a new message from {sender.get_full_name() or sender.email}"
        
        context_data = {
            'message_id': str(message.id),
            'conversation_id': str(message.conversation.id),
            'order_id': message.conversation.order.order_id,
            'sender_id': str(sender.id),
            'sender_name': sender.get_full_name() or sender.email,
            'preview': message.content[:100] + ('...' if len(message.content) > 100 else '')
        }
        
        action_url = f"/orders/{message.conversation.order.order_id}/messages"
        
        return NotificationService.create_notification(
            user=user,
            title=title,
            message=notification_message,
            notification_type='info',
            channels='all',
            priority=2,
            context_data=context_data,
            action_url=action_url,
            action_text='View Message'
        )
    
    @staticmethod
    def create_system_notification(
        user,
        message: str,
        context: Optional[Dict] = None,
        priority: int = 2
    ) -> Notification:
        """
        Create system notification.
        
        Args:
            user: Recipient user
            message: Notification message
            context: Additional context
            priority: Priority level
        
        Returns:
            Created Notification instance
        """
        title = "System Notification"
        
        return NotificationService.create_notification(
            user=user,
            title=title,
            message=message,
            notification_type='system' if priority < 3 else 'alert',
            channels='all',
            priority=priority,
            context_data=context or {},
            action_url=None,
            action_text=None
        )
    
    @staticmethod
    def create_order_notification(
        user,
        order,
        notification_type: str,
        message: str,
        context: Optional[Dict] = None
    ) -> Notification:
        """
        Create order-related notification.
        
        Args:
            user: Recipient user
            order: Related order
            notification_type: Type of notification
            message: Notification message
            context: Additional context
        
        Returns:
            Created Notification instance
        """
        title_map = {
            'assigned': "Writer Assigned",
            'in_progress': "Order in Progress",
            'delivered': "Order Delivered",
            'revision_requested': "Revision Requested",
            'completed': "Order Completed",
            'disputed': "Order Disputed",
            'deadline_warning': "Deadline Approaching",
            'deadline_missed': "Deadline Missed",
        }
        
        title = title_map.get(notification_type, "Order Update")
        
        context_data = {
            'order_id': order.order_id,
            'order_status': order.status,
            'deadline': order.deadline.isoformat() if order.deadline else None,
            **(context or {})
        }
        
        action_url = f"/orders/{order.order_id}"
        
        return NotificationService.create_notification(
            user=user,
            title=title,
            message=message,
            notification_type='info',
            channels='all',
            priority=3 if 'deadline' in notification_type else 2,
            context_data=context_data,
            action_url=action_url,
            action_text='View Order'
        )
    
    @staticmethod
    def create_payment_notification(
        user,
        payment,
        notification_type: str = 'payment_received'
    ) -> Notification:
        """
        Create payment-related notification.
        
        Args:
            user: Recipient user
            payment: Related payment
            notification_type: Type of payment notification
        
        Returns:
            Created Notification instance
        """
        title_map = {
            'payment_received': "Payment Received",
            'payment_released': "Payment Released",
            'refund_issued': "Refund Issued",
            'payment_failed': "Payment Failed",
        }
        
        title = title_map.get(notification_type, "Payment Update")
        
        amount_str = f"${payment.amount:.2f}"
        message = f"{title}: {amount_str} for Order #{payment.order.order_id}"
        
        context_data = {
            'payment_id': str(payment.id),
            'order_id': payment.order.order_id,
            'amount': str(payment.amount),
            'currency': payment.currency,
            'payment_method': payment.payment_method,
            'transaction_id': payment.transaction_id,
        }
        
        action_url = f"/payments/{payment.id}"
        
        return NotificationService.create_notification(
            user=user,
            title=title,
            message=message,
            notification_type='success' if 'failed' not in notification_type else 'error',
            channels='all',
            priority=2,
            context_data=context_data,
            action_url=action_url,
            action_text='View Payment'
        )
    
    @staticmethod
    def mark_notification_as_read(notification_id: str, user) -> bool:
        """
        Mark a notification as read.
        
        Args:
            notification_id: UUID of notification
            user: User marking as read
        
        Returns:
            True if successful, False otherwise
        """
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False
    
    @staticmethod
    def mark_all_as_read(user) -> int:
        """
        Mark all notifications as read for a user.
        
        Args:
            user: The user
        
        Returns:
            Number of notifications marked as read
        """
        count = Notification.objects.filter(user=user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return count
    
    @staticmethod
    def get_unread_count(user) -> int:
        """
        Get count of unread notifications for a user.
        
        Args:
            user: The user
        
        Returns:
            Number of unread notifications
        """
        return Notification.objects.filter(user=user, is_read=False).count()
    
    @staticmethod
    def get_recent_notifications(user, limit=10) -> List[Notification]:
        """
        Get recent notifications for a user.
        
        Args:
            user: The user
            limit: Maximum number of notifications to return
        
        Returns:
            List of notifications
        """
        return list(
            Notification.objects.filter(user=user)
            .order_by('-created_at')
            .select_related('user')[:limit]
        )


class EmailService:
    """Service for handling email notifications"""
    
    @staticmethod
    def send_email(
        recipient_email: str,
        subject: str,
        html_content: str,
        plain_text_content: str,
        recipient_user=None,
        context: Optional[Dict] = None,
        template_name: Optional[str] = None,
        priority: int = 2
    ) -> bool:
        """
        Send an email notification.
        
        Args:
            recipient_email: Recipient email address
            subject: Email subject
            html_content: HTML email content
            plain_text_content: Plain text email content
            recipient_user: User object (optional)
            context: Context data for logging
            template_name: Template name (optional)
            priority: Email priority
        
        Returns:
            True if sent successfully, False otherwise
        """
        # Check rate limiting for user
        if recipient_user:
            pref, _ = NotificationPreference.objects.get_or_create(user=recipient_user)
            if not pref.can_send_email():
                logger.warning(f"Email rate limit exceeded for {recipient_email}")
                return False
        
        try:
            # Create email
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],
                reply_to=[settings.SUPPORT_EMAIL] if hasattr(settings, 'SUPPORT_EMAIL') else None
            )
            
            # Attach HTML version
            email.attach_alternative(html_content, "text/html")
            
            # Send email
            email.send(fail_silently=False)
            
            # Log successful send
            log_entry = NotificationLog.objects.create(
                recipient_email=recipient_email,
                recipient_id=recipient_user.id if recipient_user else None,
                channel='email',
                status='sent',
                subject=subject,
                message_preview=plain_text_content[:200],
                provider='django_smtp',
                sent_at=timezone.now(),
                delivered_at=timezone.now(),  # Assume delivered immediately
            )
            
            # Update user's email count
            if recipient_user:
                pref.increment_email_count()
            
            logger.info(f"Email sent to {recipient_email}: {subject}")
            return True
            
        except Exception as e:
            # Log failure
            NotificationLog.objects.create(
                recipient_email=recipient_email,
                recipient_id=recipient_user.id if recipient_user else None,
                channel='email',
                status='failed',
                subject=subject,
                message_preview=plain_text_content[:200],
                error_message=str(e)[:500],
                sent_at=timezone.now(),
            )
            
            logger.error(f"Failed to send email to {recipient_email}: {e}")
            return False
    
    @staticmethod
    def send_templated_email(
        recipient_email: str,
        template_name: str,
        context: Dict[str, Any],
        recipient_user=None,
        priority: int = 2
    ) -> bool:
        """
        Send email using a template.
        
        Args:
            recipient_email: Recipient email address
            template_name: Name of email template
            context: Context data for template
            recipient_user: User object (optional)
            priority: Email priority
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Get template
            template = EmailTemplate.objects.get(name=template_name, is_active=True)
            
            # Prepare context
            full_context = {
                'site_name': settings.SITE_NAME if hasattr(settings, 'SITE_NAME') else 'EBWriting',
                'site_url': settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://ebwriting.com',
                'support_email': settings.SUPPORT_EMAIL if hasattr(settings, 'SUPPORT_EMAIL') else 'support@ebwriting.com',
                'current_year': timezone.now().year,
                **context
            }
            
            # Render templates
            subject = template.subject.format(**full_context)
            html_content = template.body_template.format(**full_context)
            plain_text_content = template.plain_text_template.format(**full_context)
            
            # Send email
            return EmailService.send_email(
                recipient_email=recipient_email,
                subject=subject,
                html_content=html_content,
                plain_text_content=plain_text_content,
                recipient_user=recipient_user,
                context=context,
                template_name=template_name,
                priority=priority
            )
            
        except EmailTemplate.DoesNotExist:
            logger.error(f"Email template not found: {template_name}")
            return False
        except Exception as e:
            logger.error(f"Error sending templated email to {recipient_email}: {e}")
            return False
    
    @staticmethod
    def send_welcome_email(user) -> bool:
        """Send welcome email to new user"""
        context = {
            'user_name': user.get_full_name() or user.email,
            'email': user.email,
        }
        
        return EmailService.send_templated_email(
            recipient_email=user.email,
            template_name='welcome_email',
            context=context,
            recipient_user=user,
            priority=2
        )
    
    @staticmethod
    def send_order_confirmation(user, order) -> bool:
        """Send order confirmation email"""
        context = {
            'user_name': user.get_full_name() or user.email,
            'order_id': order.order_id,
            'order_title': order.title,
            'deadline': order.deadline.strftime('%B %d, %Y') if order.deadline else 'Not specified',
            'amount': f"${order.total_amount:.2f}",
        }
        
        return EmailService.send_templated_email(
            recipient_email=user.email,
            template_name='order_confirmation',
            context=context,
            recipient_user=user,
            priority=2
        )


class PushNotificationService:
    """Service for handling push notifications"""
    
    @staticmethod
    def send_push_notification(
        user,
        title: str,
        body: str,
        data: Optional[Dict] = None
    ) -> bool:
        """
        Send push notification to user.
        
        Args:
            user: Recipient user
            title: Notification title
            body: Notification body
            data: Additional data
        
        Returns:
            True if sent successfully, False otherwise
        """
        # Check if push notifications are enabled for user
        try:
            pref = NotificationPreference.objects.get(user=user)
            if not pref.push_enabled:
                return False
        except NotificationPreference.DoesNotExist:
            pass
        
        # In a real implementation, this would integrate with FCM/APNS
        # For now, we'll log and return True
        logger.info(f"Push notification to {user.email}: {title} - {body}")
        
        # Log the push notification
        NotificationLog.objects.create(
            recipient_email=user.email,
            recipient_id=user.id,
            channel='push',
            status='sent',
            subject=title,
            message_preview=body[:200],
            sent_at=timezone.now(),
        )
        
        return True


class NotificationAnalyticsService:
    """Service for notification analytics"""
    
    @staticmethod
    def get_delivery_stats(start_date=None, end_date=None) -> Dict:
        """
        Get notification delivery statistics.
        
        Args:
            start_date: Start date for filter
            end_date: End date for filter
        
        Returns:
            Dictionary of statistics
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        logs = NotificationLog.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        total = logs.count()
        sent = logs.filter(status='sent').count()
        failed = logs.filter(status='failed').count()
        
        by_channel = logs.values('channel').annotate(
            count=models.Count('id'),
            sent=models.Count('id', filter=models.Q(status='sent')),
            failed=models.Count('id', filter=models.Q(status='failed'))
        )
        
        # Daily delivery rate
        daily_stats = logs.filter(status='sent').extra(
            {'date': "DATE(created_at)"}
        ).values('date').annotate(count=models.Count('id')).order_by('date')
        
        return {
            'total': total,
            'sent': sent,
            'failed': failed,
            'success_rate': (sent / total * 100) if total > 0 else 0,
            'by_channel': list(by_channel),
            'daily_stats': list(daily_stats),
            'period': {
                'start': start_date,
                'end': end_date
            }
        }
    
    @staticmethod
    def get_user_engagement(user, days=30) -> Dict:
        """
        Get user engagement statistics.
        
        Args:
            user: The user
            days: Number of days to analyze
        
        Returns:
            Dictionary of engagement statistics
        """
        from_date = timezone.now() - timedelta(days=days)
        
        notifications = Notification.objects.filter(
            user=user,
            created_at__gte=from_date
        )
        
        total = notifications.count()
        read = notifications.filter(is_read=True).count()
        unread = notifications.filter(is_read=False).count()
        
        # Average time to read
        read_notifications = notifications.filter(is_read=True, read_at__isnull=False)
        avg_read_time = None
        if read_notifications.exists():
            total_seconds = sum(
                (n.read_at - n.created_at).total_seconds()
                for n in read_notifications
            )
            avg_read_time = total_seconds / read_notifications.count() / 3600  # in hours
        
        # Channel distribution
        channel_dist = notifications.values('channels').annotate(
            count=models.Count('id'),
            read_count=models.Count('id', filter=models.Q(is_read=True))
        )
        
        return {
            'total_notifications': total,
            'read_notifications': read,
            'unread_notifications': unread,
            'read_rate': (read / total * 100) if total > 0 else 0,
            'avg_time_to_read_hours': avg_read_time,
            'channel_distribution': list(channel_dist),
            'period_days': days
        }