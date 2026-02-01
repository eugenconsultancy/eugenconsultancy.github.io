# apps/notifications/signals.py
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from apps.orders.models import Order
from apps.messaging.models import Message
from apps.payments.models import Payment
from apps.notifications.services import NotificationService

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=Order)
def notify_order_status_change(sender, instance, created, **kwargs):
    """
    Send notifications on order status changes.
    """
    if created:
        return  # Skip notifications for new orders (handled separately)
    
    # Get the old status from the database
    try:
        old_order = Order.objects.get(id=instance.id)
        old_status = old_order.status
    except Order.DoesNotExist:
        old_status = None
    
    # Check if status changed
    if old_status != instance.status:
        # Notify client
        message = f"Your order #{instance.order_id} status changed to {instance.status}"
        NotificationService.create_order_notification(
            user=instance.client,
            order=instance,
            notification_type=instance.status,
            message=message
        )
        
        # Notify writer if assigned
        if instance.assigned_writer:
            NotificationService.create_order_notification(
                user=instance.assigned_writer,
                order=instance,
                notification_type=instance.status,
                message=f"Order #{instance.order_id} status changed to {instance.status}"
            )
        
        logger.info(f"Order status notification sent for order {instance.order_id}")


@receiver(post_save, sender=Message)
def notify_new_message(sender, instance, created, **kwargs):
    """
    Send notifications for new messages.
    """
    if not created or instance.is_system_message:
        return
    
    # Get conversation participants
    conversation = instance.conversation
    participants = conversation.participants
    
    # Notify all participants except sender
    for participant in participants:
        if participant != instance.sender:
            NotificationService.create_message_notification(
                user=participant,
                message=instance,
                sender=instance.sender
            )
    
    logger.info(f"Message notification sent for message {instance.id}")


@receiver(post_save, sender=Payment)
def notify_payment_update(sender, instance, created, **kwargs):
    """
    Send notifications for payment updates.
    """
    if created:
        # New payment notification
        NotificationService.create_payment_notification(
            user=instance.user,
            payment=instance,
            notification_type='payment_received'
        )
    else:
        # Payment status change
        try:
            old_payment = Payment.objects.get(id=instance.id)
            old_status = old_payment.status
        except Payment.DoesNotExist:
            old_status = None
        
        if old_status != instance.status:
            notification_type = {
                'released': 'payment_released',
                'refunded': 'refund_issued',
                'failed': 'payment_failed',
            }.get(instance.status)
            
            if notification_type:
                NotificationService.create_payment_notification(
                    user=instance.user,
                    payment=instance,
                    notification_type=notification_type
                )
    
    logger.info(f"Payment notification sent for payment {instance.id}")


@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance, created, **kwargs):
    """
    Create notification preferences for new users.
    """
    if created:
        from apps.notifications.models import NotificationPreference
        NotificationPreference.objects.get_or_create(user=instance)
        logger.info(f"Notification preferences created for user {instance.email}")