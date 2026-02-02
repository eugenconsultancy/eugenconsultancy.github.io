import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from apps.messaging.models import Message, Conversation
from apps.orders.models import Order

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def create_conversation_on_order_assignment(sender, instance, created, **kwargs):
    """
    Create conversation when a writer is assigned to an order.
    """
    # Changed 'assigned_writer' to 'writer'
    if instance.writer and not hasattr(instance, 'conversation'):
        from apps.messaging.services import ConversationService
        try:
            conversation = ConversationService.get_or_create_conversation(instance)
            logger.info(f"Conversation created for order {instance.order_number}")
            
            # Send welcome message - using instance.writer
            writer_name = instance.writer.get_full_name() or instance.writer.username
            ConversationService.send_system_message(
                conversation=conversation,
                content=f"Writer {writer_name} has been assigned to your order. "
                        f"You can now communicate securely about the order requirements."
            )
        except Exception as e:
            logger.error(f"Failed to create conversation for order {instance.id}: {e}")


@receiver(pre_save, sender=Message)
def update_conversation_timestamp(sender, instance, **kwargs):
    """
    Update conversation's updated_at timestamp when new message is sent.
    """
    if instance.pk is None:  # New message
        try:
            conversation = instance.conversation
            conversation.updated_at = timezone.now()
            conversation.save(update_fields=['updated_at'])
        except Exception as e:
            logger.error(f"Failed to update conversation timestamp: {e}")