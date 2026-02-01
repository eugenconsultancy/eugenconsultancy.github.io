# apps/messaging/models.py
import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import FileExtensionValidator

from apps.orders.models import Order


class Conversation(models.Model):
    """
    Order-scoped conversation between client and writer.
    Admin has full visibility to all conversations.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='conversation',
        help_text="Order this conversation belongs to"
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_closed = models.BooleanField(default=False, help_text="Whether conversation is closed")
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'
        indexes = [
            models.Index(fields=['order', 'created_at']),
            models.Index(fields=['is_closed', 'updated_at']),
        ]
    
    def __str__(self):
        return f"Conversation for Order #{self.order.order_id}"
    
    @property
    def participants(self):
        """Get all participants in this conversation"""
        participants = {self.order.client}
        if self.order.assigned_writer:
            participants.add(self.order.assigned_writer)
        return participants
    
    def close(self):
        """Close the conversation"""
        self.is_closed = True
        self.save(update_fields=['is_closed', 'updated_at'])


class Message(models.Model):
    """
    Individual message within a conversation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    content = models.TextField(max_length=5000, help_text="Message content")
    
    # System message flag
    is_system_message = models.BooleanField(
        default=False,
        help_text="Whether this is a system-generated message"
    )
    
    # Message status tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Admin visibility tracking
    admin_has_viewed = models.BooleanField(default=False)
    admin_viewed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
            models.Index(fields=['is_read', 'created_at']),
        ]
    
    def __str__(self):
        return f"Message from {self.sender.email} at {self.created_at}"
    
    def mark_as_read(self, user):
        """Mark message as read by recipient"""
        if not self.is_read and user != self.sender:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_viewed_by_admin(self):
        """Mark message as viewed by admin"""
        if not self.admin_has_viewed:
            self.admin_has_viewed = True
            self.admin_viewed_at = timezone.now()
            self.save(update_fields=['admin_has_viewed', 'admin_viewed_at'])


class MessageAttachment(models.Model):
    """
    File attachments for messages with strict security controls.
    """
    ALLOWED_EXTENSIONS = [
        '.pdf', '.doc', '.docx', '.txt', '.rtf',
        '.jpg', '.jpeg', '.png', '.gif',
        '.xls', '.xlsx', '.ppt', '.pptx'
    ]
    
    ALLOWED_MIME_TYPES = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'text/rtf',
        'image/jpeg',
        'image/png',
        'image/gif',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(
        upload_to='message_attachments/%Y/%m/%d/',
        validators=[
            FileExtensionValidator(allowed_extensions=[
                'pdf', 'doc', 'docx', 'txt', 'rtf',
                'jpg', 'jpeg', 'png', 'gif',
                'xls', 'xlsx', 'ppt', 'pptx'
            ])
        ],
        help_text="Attached file"
    )
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=100)
    
    # Security tracking
    virus_scan_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('clean', 'Clean'),
            ('infected', 'Infected'),
            ('error', 'Scan Error')
        ],
        default='pending'
    )
    virus_scan_result = models.TextField(null=True, blank=True)
    scanned_at = models.DateTimeField(null=True, blank=True)
    
    # Integrity checks
    file_hash = models.CharField(max_length=64, help_text="SHA-256 hash of file")
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = 'Message Attachment'
        verbose_name_plural = 'Message Attachments'
        indexes = [
            models.Index(fields=['message', 'created_at']),
            models.Index(fields=['virus_scan_status']),
        ]
    
    def __str__(self):
        return f"{self.original_filename} ({self.file_type})"
    
    def save(self, *args, **kwargs):
        # Ensure file size is within limits (10MB)
        if self.file.size > 10 * 1024 * 1024:  # 10MB
            raise ValueError("File size exceeds 10MB limit")
        super().save(*args, **kwargs)


class MessageReadReceipt(models.Model):
    """
    Track read receipts for messages.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='read_receipts'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    read_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ['message', 'user']
        verbose_name = 'Read Receipt'
        verbose_name_plural = 'Read Receipts'
        indexes = [
            models.Index(fields=['message', 'user']),
            models.Index(fields=['user', 'read_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} read message at {self.read_at}"