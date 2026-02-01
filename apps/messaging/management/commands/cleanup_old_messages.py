# apps/messaging/management/commands/cleanup_old_messages.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from apps.messaging.models import Conversation, Message, MessageAttachment
from apps.orders.models import Order

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up old messages and conversations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Clean up data older than specified days (default: 365)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(f"Cleaning up data older than {days} days (before {cutoff_date.date()})")
        
        # Find completed orders older than cutoff
        completed_orders = Order.objects.filter(
            status__in=['completed', 'cancelled', 'refunded'],
            updated_at__lt=cutoff_date
        )
        
        # Get conversations for these orders
        conversations = Conversation.objects.filter(order__in=completed_orders)
        
        # Get messages and attachments
        messages = Message.objects.filter(conversation__in=conversations)
        attachments = MessageAttachment.objects.filter(message__in=messages)
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No data will be deleted"))
            self.stdout.write(f"Conversations to delete: {conversations.count()}")
            self.stdout.write(f"Messages to delete: {messages.count()}")
            self.stdout.write(f"Attachments to delete: {attachments.count()}")
            
            # Show sample of what would be deleted
            if conversations.exists():
                self.stdout.write("\nSample conversations to delete:")
                for conv in conversations[:5]:
                    self.stdout.write(f"  - Conversation for Order #{conv.order.order_id} (Created: {conv.created_at.date()})")
            
            if attachments.exists():
                self.stdout.write("\nSample attachments to delete:")
                for att in attachments[:5]:
                    self.stdout.write(f"  - {att.original_filename} ({att.file_size} bytes)")
        else:
            # Actually delete the data
            attachment_count = attachments.count()
            message_count = messages.count()
            conversation_count = conversations.count()
            
            # Delete attachments (and their files)
            for attachment in attachments:
                try:
                    # Delete the actual file
                    attachment.file.delete(save=False)
                except Exception as e:
                    logger.error(f"Error deleting file {attachment.file.path}: {e}")
                
                # Delete the database record
                attachment.delete()
            
            # Delete messages
            messages.delete()
            
            # Delete conversations
            conversations.delete()
            
            self.stdout.write(self.style.SUCCESS(
                f"Cleaned up: {attachment_count} attachments, "
                f"{message_count} messages, "
                f"{conversation_count} conversations"
            ))
            
            logger.info(
                f"Message cleanup completed: "
                f"{attachment_count} attachments, "
                f"{message_count} messages, "
                f"{conversation_count} conversations deleted"
            )