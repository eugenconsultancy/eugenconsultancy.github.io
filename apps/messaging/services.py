# apps/messaging/services.py
import hashlib
import logging
from typing import Optional, List, Tuple
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.db import models

from apps.messaging.models import (
    Conversation, Message, MessageAttachment, MessageReadReceipt
)
from apps.orders.models import Order
from apps.notifications.services import NotificationService

logger = logging.getLogger(__name__)


class MessageSecurityService:
    """Service for handling message security and validation"""
    
    @staticmethod
    def validate_attachment(file_obj) -> Tuple[bool, str]:
        """
        Validate attachment file security.
        Returns: Tuple of (is_valid, error_message)
        """
        # Check file size (10MB limit)
        if file_obj.size > 10 * 1024 * 1024:
            return False, "File size exceeds 10MB limit"
        
        # Check file type
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_obj.name)
        
        # Ensure ALLOWED_MIME_TYPES exists on MessageAttachment model
        allowed_types = getattr(MessageAttachment, 'ALLOWED_MIME_TYPES', [])
        if allowed_types and mime_type not in allowed_types:
            return False, f"File type {mime_type} is not allowed"
        
        return True, ""
    
    @staticmethod
    def calculate_file_hash(file_obj) -> str:
        """Calculate SHA-256 hash of file"""
        sha256_hash = hashlib.sha256()
        for chunk in file_obj.chunks():
            sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    @staticmethod
    def scan_for_viruses(file_path: str) -> Tuple[str, Optional[str]]:
        """Scan file for viruses using ClamAV"""
        try:
            import pyclamd
            cd = pyclamd.ClamdUnixSocket()
            if not cd.ping():
                cd = pyclamd.ClamdNetworkSocket()
                
            scan_result = cd.scan_file(file_path)
            if scan_result is None:
                return 'clean', None
            else:
                virus_name = list(scan_result.values())[0][1]
                return 'infected', f"Virus detected: {virus_name}"
        except (ImportError, Exception) as e:
            logger.warning(f"Virus scan skipped or failed: {e}")
            return 'pending', str(e)


class ConversationService:
    """Service for managing conversations"""
    
    @staticmethod
    @transaction.atomic
    def get_or_create_conversation(order: Order) -> Conversation:
        """Get or create conversation for an order"""
        conversation, created = Conversation.objects.get_or_create(order=order)
        
        if created:
            # Create initial system message - Fix: Using order_number
            Message.objects.create(
                conversation=conversation,
                sender=None, 
                content=f"Conversation started for order #{order.order_number}",
                is_system_message=True
            )
            logger.info(f"Created new conversation for order {order.order_number}")
        
        return conversation
    
    @staticmethod
    def get_conversation_messages(conversation: Conversation, user=None, limit=50):
        """Get messages for a conversation with proper authorization"""
        if user:
            # Assumes 'participants' is a property/method on Conversation model
            if user not in conversation.participants and not user.is_staff:
                raise PermissionError("User not authorized to view this conversation")
        
        messages = conversation.messages.select_related(
            'sender', 'conversation__order'
        ).prefetch_related('attachments').order_by('-created_at')[:limit]
        
        if user and user.is_staff:
            unviewed_messages = messages.filter(admin_has_viewed=False)
            for msg in unviewed_messages:
                msg.mark_as_viewed_by_admin()
        
        return messages
    
    @staticmethod
    @transaction.atomic
    def send_message(
        conversation: Conversation,
        sender,
        content: str,
        attachments=None
    ) -> Message:
        """Send a message in a conversation"""
        # Fix: Corrected typo 'particversation'
        if sender not in conversation.participants:
            raise ValueError("Sender is not a participant in this conversation")
        
        if conversation.is_closed:
            raise ValueError("Cannot send message to closed conversation")
        
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content.strip(),
            is_system_message=False
        )
        
        if attachments:
            for attachment_file in attachments:
                MessageAttachmentService.create_attachment(
                    message=message,
                    file_obj=attachment_file
                )
        
        conversation.save(update_fields=['updated_at'])
        
        for participant in conversation.participants:
            if participant != sender:
                NotificationService.create_message_notification(
                    user=participant,
                    message=message,
                    sender=sender
                )
        
        return message
    
    @staticmethod
    @transaction.atomic
    def send_system_message(conversation: Conversation, content: str) -> Message:
        """Send a system-generated message"""
        message = Message.objects.create(
            conversation=conversation,
            sender=None,
            content=content,
            is_system_message=True
        )
        conversation.save(update_fields=['updated_at'])
        
        for participant in conversation.participants:
            NotificationService.create_system_notification(
                user=participant,
                message=content,
                context={"conversation_id": str(conversation.id)}
            )
        return message

    @staticmethod
    @transaction.atomic
    def mark_message_as_read(message: Message, user):
        """Mark a message as read by a user"""
        if user == message.sender:
            return 
        
        receipt, created = MessageReadReceipt.objects.get_or_create(
            message=message,
            user=user,
            defaults={'read_at': timezone.now()}
        )
        
        if created:
            message.is_read = True
            message.read_at = timezone.now()
            message.save(update_fields=['is_read', 'read_at'])


class MessageAttachmentService:
    """Service for handling message attachments"""
    
    @staticmethod
    @transaction.atomic
    def create_attachment(message: Message, file_obj) -> MessageAttachment:
        """Create and validate a message attachment"""
        is_valid, error = MessageSecurityService.validate_attachment(file_obj)
        if not is_valid:
            raise ValueError(f"Invalid attachment: {error}")
        
        file_hash = MessageSecurityService.calculate_file_hash(file_obj)
        
        attachment = MessageAttachment.objects.create(
            message=message,
            file=file_obj,
            original_filename=file_obj.name,
            file_size=file_obj.size,
            file_type=getattr(file_obj, 'content_type', 'application/octet-stream'),
            file_hash=file_hash
        )
        
        # Async task call
        from apps.messaging.tasks import scan_attachment_for_viruses
        scan_attachment_for_viruses.delay(str(attachment.id))
        
        return attachment


class ConversationAnalyticsService:
    """Service for conversation analytics and reporting"""
    
    @staticmethod
    def get_conversation_stats(conversation: Conversation) -> dict:
        messages = conversation.messages.all()
        return {
            'total_messages': messages.count(),
            'system_messages': messages.filter(is_system_message=True).count(),
            'user_messages': messages.filter(is_system_message=False).count(),
            'last_activity': conversation.updated_at,
        }
    
    @staticmethod
    def get_user_conversation_stats(user, days=30):
        """Get conversation statistics for a user"""
        from_date = timezone.now() - timedelta(days=days)
        
        # Fix: Changed assigned_writer to writer
        conversations = Conversation.objects.filter(
            order__in=Order.objects.filter(
                models.Q(client=user) | 
                models.Q(writer=user)
            ),
            created_at__gte=from_date
        )
        
        stats = {
            'total_conversations': conversations.count(),
            'active_conversations': conversations.filter(is_closed=False).count(),
            'messages_sent': Message.objects.filter(
                sender=user,
                conversation__in=conversations,
                created_at__gte=from_date
            ).count()
        }
        return stats