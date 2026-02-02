import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.orders.models import Order
from apps.messaging.models import Message
from apps.payments.models import Payment
from apps.notifications.websocket_utils import WebSocketNotificationService
from apps.notifications.services import NotificationService
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def send_order_update_websocket(sender, instance, created, **kwargs):
    """
    Send order update via WebSocket.
    """
    if created:
        return  # Skip notifications for new orders
    
    try:
        # FIXED: Use .values() to look up the previous state safely
        old_instance = Order.objects.filter(id=instance.id).values('state').first()
        old_state = old_instance['state'] if old_instance else None
    except Exception:
        old_state = None
    
    # FIXED: Changed .status to .state
    if old_state != instance.state:
        # Data payload for the client
        # FIXED: Changed order_id to order_number
        payload = {
            'order_id': instance.order_number,
            'order_title': instance.title,
            'status': instance.state,
            'old_status': old_state,
            'message': f'Order status changed to {instance.get_state_display()}',
            'action_url': f'/orders/{instance.order_number}'
        }

        # Notify client
        WebSocketNotificationService.send_order_update(
            user_id=str(instance.client.id),
            order_data=payload
        )
        
        # Notify writer if assigned (FIXED: changed assigned_writer to writer)
        if instance.writer:
            WebSocketNotificationService.send_order_update(
                user_id=str(instance.writer.id),
                order_data=payload
            )


@receiver(post_save, sender=Message)
def send_new_message_websocket(sender, instance, created, **kwargs):
    """
    Send new message notification via WebSocket.
    """
    if not created or instance.is_system_message:
        return
    
    # Get conversation participants
    conversation = instance.conversation
    participants = conversation.participants.all()
    
    # Send WebSocket notification to all participants except sender
    for participant in participants:
        if participant != instance.sender:
            WebSocketNotificationService.send_new_message(
                user_id=str(participant.id),
                message_data={
                    'message_id': str(instance.id),
                    'conversation_id': str(conversation.id),
                    'order_id': conversation.order.order_number, # FIXED: order_id to order_number
                    'sender_id': str(instance.sender.id),
                    'sender_name': instance.sender.get_full_name() or instance.sender.email,
                    'preview': instance.content[:100] + ('...' if len(instance.content) > 100 else ''),
                    'action_url': f'/orders/{conversation.order.order_number}/messages'
                }
            )


@receiver(post_save, sender=Payment)
def send_payment_update_websocket(sender, instance, created, **kwargs):
    """
    Send payment update via WebSocket.
    """
    order_number = instance.order.order_number if instance.order else None

    if created:
        # New payment notification
        WebSocketNotificationService.send_payment_update(
            user_id=str(instance.user.id),
            payment_data={
                'payment_id': str(instance.id),
                'order_id': order_number,
                'status': instance.status,
                'amount': str(instance.amount),
                'currency': instance.currency,
                'message': f'Payment received: ${instance.amount:.2f}',
                'action_url': f'/payments/{instance.id}'
            }
        )
    else:
        # Payment status change
        try:
            old_payment = Payment.objects.filter(id=instance.id).values('status').first()
            old_status = old_payment['status'] if old_payment else None
        except Exception:
            old_status = None
        
        if old_status != instance.status:
            message_map = {
                'released': 'Payment released to writer',
                'refunded': 'Payment refunded',
                'failed': 'Payment failed',
            }
            
            message = message_map.get(instance.status, f'Payment status: {instance.status}')
            
            WebSocketNotificationService.send_payment_update(
                user_id=str(instance.user.id),
                payment_data={
                    'payment_id': str(instance.id),
                    'order_id': order_number,
                    'status': instance.status,
                    'amount': str(instance.amount),
                    'currency': instance.currency,
                    'message': message,
                    'action_url': f'/payments/{instance.id}'
                }
            )


@receiver(post_save, sender=Notification)
def send_notification_websocket(sender, instance, created, **kwargs):
    """
    Send notification via WebSocket when created.
    """
    if created and instance.channels in ['push', 'all']:
        try:
            # Get unread count
            unread_count = NotificationService.get_unread_count(instance.user)
            
            # Determine category
            category = 'system'
            context_data = instance.context_data or {}
            
            if 'category' in context_data:
                category = context_data['category']
            elif 'order_number' in context_data or 'order_id' in context_data:
                category = 'order_updates'
            elif 'message_id' in context_data:
                category = 'messages'
            elif 'payment_id' in context_data:
                category = 'payments'
            
            # Send via WebSocket
            WebSocketNotificationService.send_notification_to_user(
                user_id=str(instance.user.id),
                notification_data={
                    'id': str(instance.id),
                    'title': instance.title,
                    'message': instance.message,
                    'category': category,
                    'notification_type': instance.notification_type,
                    'priority': instance.priority,
                    'action_url': instance.action_url,
                    'action_text': instance.action_text,
                    'context_data': context_data,
                    'timestamp': instance.created_at.isoformat(),
                    'unread_count': unread_count
                }
            )
            
        except Exception as e:
            logger.error(f"Error sending WebSocket notification for {instance.id}: {e}")