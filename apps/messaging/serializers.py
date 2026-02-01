# apps/messaging/serializers.py
from rest_framework import serializers
from django.utils import timezone

from apps.messaging.models import (
    Conversation, 
    Message, 
    MessageAttachment,
    MessageReadReceipt
)
from apps.accounts.models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details in messages."""
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'user_type']
        read_only_fields = fields


class AttachmentSerializer(serializers.ModelSerializer):
    """Serializer for message attachments."""
    
    download_url = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = MessageAttachment
        fields = [
            'id', 'original_filename', 'file_type', 
            'file_size', 'file_size_mb', 'virus_scan_status',
            'scanned_at', 'download_url', 'created_at'
        ]
        read_only_fields = fields
    
    def get_download_url(self, obj):
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None
    
    def get_file_size_mb(self, obj):
        if obj.file_size:
            return f"{obj.file_size / 1024 / 1024:.2f} MB"
        return None


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for messages."""
    
    sender = UserSerializer(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    is_read_by_me = serializers.SerializerMethodField()
    read_receipts = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'content', 'is_system_message',
            'is_read', 'read_at', 'is_read_by_me', 'read_receipts',
            'admin_has_viewed', 'admin_viewed_at',
            'attachments', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_is_read_by_me(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return MessageReadReceipt.objects.filter(
                message=obj,
                user=request.user
            ).exists()
        return False
    
    def get_read_receipts(self, obj):
        receipts = MessageReadReceipt.objects.filter(message=obj).select_related('user')
        return [
            {
                'user_id': str(receipt.user.id),
                'user_email': receipt.user.email,
                'read_at': receipt.read_at
            }
            for receipt in receipts
        ]


class SendMessageSerializer(serializers.Serializer):
    """Serializer for sending new messages."""
    
    content = serializers.CharField(
        max_length=5000,
        min_length=1,
        required=True,
        error_messages={
            'required': 'Message content is required',
            'min_length': 'Message cannot be empty',
            'max_length': 'Message cannot exceed 5000 characters'
        }
    )
    attachments = serializers.ListField(
        child=serializers.FileField(
            max_length=10 * 1024 * 1024,  # 10MB
            allow_empty_file=False
        ),
        required=False,
        max_length=5  # Max 5 attachments per message
    )
    
    def validate_content(self, value):
        """Validate message content."""
        content = value.strip()
        if not content:
            raise serializers.ValidationError("Message cannot be empty")
        return content
    
    def validate_attachments(self, files):
        """Validate attachments."""
        if files:
            if len(files) > 5:
                raise serializers.ValidationError("Maximum 5 attachments allowed per message")
            
            for file in files:
                # Check file size
                if file.size > 10 * 1024 * 1024:  # 10MB
                    raise serializers.ValidationError(
                        f"File {file.name} exceeds 10MB limit"
                    )
                
                # Check file type
                import mimetypes
                mime_type, _ = mimetypes.guess_type(file.name)
                
                allowed_mime_types = MessageAttachment.ALLOWED_MIME_TYPES
                if mime_type not in allowed_mime_types:
                    raise serializers.ValidationError(
                        f"File type {mime_type} not allowed for {file.name}"
                    )
        
        return files


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for conversations."""
    
    order_id = serializers.CharField(source='order.order_id', read_only=True)
    order_title = serializers.CharField(source='order.title', read_only=True)
    client = UserSerializer(source='order.client', read_only=True)
    writer = UserSerializer(source='order.assigned_writer', read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'order_id', 'order_title', 'client', 'writer',
            'is_closed', 'last_message', 'unread_count', 'message_count',
            'participants', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return {
                'content': last_msg.content[:100] + ('...' if len(last_msg.content) > 100 else ''),
                'sender': last_msg.sender.email if last_msg.sender else 'System',
                'sent_at': last_msg.created_at
            }
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.messages.filter(
                is_read=False
            ).exclude(
                sender=request.user
            ).count()
        return 0
    
    def get_message_count(self, obj):
        return obj.messages.count()
    
    def get_participants(self, obj):
        return [
            {
                'id': str(user.id),
                'email': user.email,
                'full_name': user.get_full_name(),
                'role': 'writer' if hasattr(user, 'writer_profile') else 'client'
            }
            for user in obj.participants
        ]