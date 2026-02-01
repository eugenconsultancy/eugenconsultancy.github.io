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
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file size (10MB limit)
        if file_obj.size > 10 * 1024 * 1024:
            return False, "File size exceeds 10MB limit"
        
        # Check file type
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_obj.name)
        
        if mime_type not in MessageAttachment.ALLOWED_MIME_TYPES:
            return False, f"File type {mime_type} is not allowed"
        
        return True, ""
    
    @staticmethod
    def calculate_file_hash(file_obj) -> str:
        """Calculate SHA-256 hash of file"""
        sha256_hash = hashlib.sha256()
        
        # Read file in chunks
        for chunk in file_obj.chunks():
            sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    @staticmethod
    def scan_for_viruses(file_path: str) -> Tuple[str, Optional[str]]:
        """
        Scan file for viruses using ClamAV.
        
        Returns:
            Tuple of (status, result_message)
        """
        try:
            # Import ClamAV if available
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
                
        except ImportError:
            logger.warning("ClamAV not installed, skipping virus scan")
            return 'pending', "ClamAV not available"
        except Exception as e:
            logger.error(f"Virus scan error: {e}")
            return 'error', str(e)


class ConversationService:
    """Service for managing conversations"""
    
    @staticmethod
    @transaction.atomic
    def get_or_create_conversation(order: Order) -> Conversation:
        """Get or create conversation for an order"""
        conversation, created = Conversation.objects.get_or_create(order=order)
        
        if created:
            # Create initial system message
            Message.objects.create(
                conversation=conversation,
                sender=order.client,
                content=f"Conversation started for order #{order.order_id}",
                is_system_message=True
            )
            
            logger.info(f"Created new conversation for order {order.order_id}")
        
        return conversation
    
    @staticmethod
    def get_conversation_messages(conversation: Conversation, user=None, limit=50):
        """
        Get messages for a conversation with proper authorization.
        
        Args:
            conversation: The conversation
            user: User requesting messages (for authorization)
            limit: Number of messages to return
        
        Returns:
            QuerySet of messages
        """
        # Check if user has access to this conversation
        if user:
            if user not in conversation.participants and not user.is_staff:
                raise PermissionError("User not authorized to view this conversation")
        
        messages = conversation.messages.select_related(
            'sender', 'conversation__order'
        ).prefetch_related('attachments')[:limit]
        
        # Mark messages as viewed by admin if admin is viewing
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
        """
        Send a message in a conversation.
        
        Args:
            conversation: The conversation
            sender: User sending the message
            content: Message content
            attachments: List of file attachments
        
        Returns:
            The created message
        """
        # Validate sender is a participant
        if sender not in conversation.particversation.participants:
            raise ValueError("Sender is not a participant in this conversation")
        
        # Check if conversation is closed
        if conversation.is_closed:
            raise ValueError("Cannot send message to closed conversation")
        
        # Create message
        message = Message.objects.create(
            conversation=conversation,
            sender=sender,
            content=content.strip(),
            is_system_message=False
        )
        
        # Handle attachments
        if attachments:
            for attachment_file in attachments:
                MessageAttachmentService.create_attachment(
                    message=message,
                    file_obj=attachment_file
                )
        
        # Update conversation timestamp
        conversation.save(update_fields=['updated_at'])
        
        # Send notifications to other participants
        participants = conversation.participants
        for participant in participants:
            if participant != sender:
                NotificationService.create_message_notification(
                    user=participant,
                    message=message,
                    sender=sender
                )
        
        logger.info(f"Message sent by {sender.email} in conversation {conversation.id}")
        return message
    
    @staticmethod
    @transaction.atomic
    def send_system_message(
        conversation: Conversation,
        content: str
    ) -> Message:
        """
        Send a system-generated message.
        
        Args:
            conversation: The conversation
            content: Message content
        
        Returns:
            The created message
        """
        message = Message.objects.create(
            conversation=conversation,
            sender=None,  # System message
            content=content,
            is_system_message=True
        )
        
        # Update conversation timestamp
        conversation.save(update_fields=['updated_at'])
        
        # Send notifications to all participants
        for participant in conversation.participants:
            NotificationService.create_system_notification(
                user=participant,
                message=content,
                context={"conversation_id": str(conversation.id)}
            )
        
        logger.info(f"System message sent in conversation {conversation.id}")
        return message
    
    @staticmethod
    @transaction.atomic
    def mark_message_as_read(message: Message, user):
        """Mark a message as read by a user"""
        if user == message.sender:
            return  # Don't create read receipt for sender
        
        receipt, created = MessageReadReceipt.objects.get_or_create(
            message=message,
            user=user,
            defaults={'read_at': timezone.now()}
        )
        
        if created:
            message.is_read = True
            message.read_at = timezone.now()
            message.save(update_fields=['is_read', 'read_at'])
            
            logger.info(f"Message {message.id} marked as read by {user.email}")


class MessageAttachmentService:
    """Service for handling message attachments"""
    
    @staticmethod
    @transaction.atomic
    def create_attachment(message: Message, file_obj) -> MessageAttachment:
        """
        Create and validate a message attachment.
        
        Args:
            message: The parent message
            file_obj: The file object
        
        Returns:
            Created MessageAttachment instance
        """
        # Validate file
        is_valid, error = MessageSecurityService.validate_attachment(file_obj)
        if not is_valid:
            raise ValueError(f"Invalid attachment: {error}")
        
        # Calculate file hash
        file_hash = MessageSecurityService.calculate_file_hash(file_obj)
        
        # Create attachment
        attachment = MessageAttachment.objects.create(
            message=message,
            file=file_obj,
            original_filename=file_obj.name,
            file_size=file_obj.size,
            file_type=file_obj.content_type or 'application/octet-stream',
            file_hash=file_hash
        )
        
        # Schedule virus scan (async)
        from apps.messaging.tasks import scan_attachment_for_viruses
        scan_attachment_for_viruses.delay(str(attachment.id))
        
        logger.info(f"Attachment created: {attachment.original_filename}")
        return attachment
    
    @staticmethod
    def get_attachment(attachment_id: str, user) -> MessageAttachment:
        """
        Get attachment with authorization check.
        
        Args:
            attachment_id: UUID of attachment
            user: User requesting the attachment
        
        Returns:
            MessageAttachment instance
        """
        try:
            attachment = MessageAttachment.objects.select_related(
                'message__conversation__order'
            ).get(id=attachment_id)
            
            # Check authorization
            if user not in attachment.message.conversation.participants and not user.is_staff:
                raise PermissionError("User not authorized to access this attachment")
            
            # Check virus scan status
            if attachment.virus_scan_status == 'infected':
                raise ValueError("File is infected with virus and cannot be downloaded")
            
            return attachment
            
        except MessageAttachment.DoesNotExist:
            raise ValueError("Attachment not found")


class ConversationAnalyticsService:
    """Service for conversation analytics and reporting"""
    
    @staticmethod
    def get_conversation_stats(conversation: Conversation) -> dict:
        """Get statistics for a conversation"""
        messages = conversation.messages.all()
        
        return {
            'total_messages': messages.count(),
            'system_messages': messages.filter(is_system_message=True).count(),
            'user_messages': messages.filter(is_system_message=False).count(),
            'attachments_count': MessageAttachment.objects.filter(
                message__conversation=conversation
            ).count(),
            'unread_messages': messages.filter(is_read=False).exclude(
                sender__in=conversation.participants
            ).count(),
            'started_at': conversation.created_at,
            'last_activity': conversation.updated_at,
            'duration_days': (timezone.now() - conversation.created_at).days
        }
    
    @staticmethod
    def get_user_conversation_stats(user, days=30):
        """Get conversation statistics for a user"""
        from_date = timezone.now() - timedelta(days=days)
        
        # Get conversations where user is a participant
        conversations = Conversation.objects.filter(
            order__in=Order.objects.filter(
                models.Q(client=user) | 
                models.Q(assigned_writer=user)
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
            ).count(),
            'attachments_sent': MessageAttachment.objects.filter(
                message__sender=user,
                created_at__gte=from_date
            ).count(),
            'avg_response_time_hours': None
        }
        
        # Calculate average response time
        response_times = []
        for conv in conversations:
            user_messages = conv.messages.filter(sender=user).order_by('created_at')
            other_messages = conv.messages.exclude(sender=user).order_by('created_at')
            
            if user_messages.exists() and other_messages.exists():
                last_user_msg = user_messages.last()
                next_response = other_messages.filter(
                    created_at__gt=last_user_msg.created_at
                ).first()
                
                if next_response:
                    response_time = (next_response.created_at - last_user_msg.created_at).total_seconds() / 3600
                    response_times.append(response_time)
        
        if response_times:
            stats['avg_response_time_hours'] = sum(response_times) / len(response_times)
        
        return stats