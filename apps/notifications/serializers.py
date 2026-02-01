# apps/notifications/serializers.py
from rest_framework import serializers
from django.utils import timezone

from apps.notifications.models import (
    Notification,
    NotificationPreference,
    EmailTemplate,
    NotificationLog
)


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications."""
    
    type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    time_since = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'notification_type', 'type_display',
            'context_data', 'action_url', 'action_text',
            'channels', 'priority', 'priority_display',
            'is_read', 'read_at', 'is_sent', 'sent_at',
            'time_since', 'created_at'
        ]
        read_only_fields = fields
    
    def get_time_since(self, obj):
        """Calculate time since notification was created."""
        delta = timezone.now() - obj.created_at
        
        if delta.days > 365:
            years = delta.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for notification preferences."""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = NotificationPreference
        fields = [
            'id', 'user_email', 'email_enabled', 'push_enabled', 'sms_enabled',
            'preferences', 'quiet_hours_enabled', 'quiet_hours_start',
            'quiet_hours_end', 'daily_email_limit', 'emails_sent_today',
            'last_reset_date', 'updated_at'
        ]
        read_only_fields = ['id', 'user_email', 'emails_sent_today', 'last_reset_date', 'updated_at']


class UpdatePreferenceSerializer(serializers.Serializer):
    """Serializer for updating notification preferences."""
    
    email_enabled = serializers.BooleanField(required=False)
    push_enabled = serializers.BooleanField(required=False)
    sms_enabled = serializers.BooleanField(required=False)
    quiet_hours_enabled = serializers.BooleanField(required=False)
    quiet_hours_start = serializers.TimeField(required=False, allow_null=True)
    quiet_hours_end = serializers.TimeField(required=False, allow_null=True)
    preferences = serializers.JSONField(required=False)
    
    def validate_quiet_hours_start(self, value):
        """Validate quiet hours start time."""
        if value and not isinstance(value, str):
            from datetime import time
            if not isinstance(value, time):
                raise serializers.ValidationError("Invalid time format")
        return value
    
    def validate_quiet_hours_end(self, value):
        """Validate quiet hours end time."""
        if value and not isinstance(value, str):
            from datetime import time
            if not isinstance(value, time):
                raise serializers.ValidationError("Invalid time format")
        return value
    
    def validate_preferences(self, value):
        """Validate preferences JSON."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Preferences must be a JSON object")
        return value


class EmailTemplateSerializer(serializers.ModelSerializer):
    """Serializer for email templates."""
    
    type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    format_display = serializers.CharField(source='get_format_display', read_only=True)
    
    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'description', 'template_type', 'type_display',
            'format', 'format_display', 'template_file', 'template_content',
            'placeholders', 'styles', 'version', 'is_active',
            'requires_signature', 'allowed_signers',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class NotificationLogSerializer(serializers.ModelSerializer):
    """Serializer for notification logs."""
    
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    time_since = serializers.SerializerMethodField()
    
    class Meta:
        model = NotificationLog
        fields = [
            'id', 'recipient_email', 'recipient_id', 'channel', 'channel_display',
            'status', 'status_display', 'subject', 'message_preview',
            'provider', 'provider_message_id', 'sent_at', 'delivered_at',
            'opened_at', 'clicked_at', 'error_message', 'retry_count',
            'time_since', 'created_at'
        ]
        read_only_fields = fields
    
    def get_time_since(self, obj):
        """Calculate time since log was created."""
        delta = timezone.now() - obj.created_at
        
        if delta.days > 365:
            years = delta.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"