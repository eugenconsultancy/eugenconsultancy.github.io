# apps/notifications/models.py
import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Notification(models.Model):
    """
    System notifications for users.
    """
    NOTIFICATION_TYPES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('alert', 'Alert'),
        ('success', 'Success'),
        ('error', 'Error'),
    ]
    
    NOTIFICATION_CHANNELS = [
        ('email', 'Email'),
        ('push', 'Push Notification'),
        ('in_app', 'In-App Notification'),
        ('sms', 'SMS'),
        ('all', 'All Channels'),
    ]
    
    PRIORITY_LEVELS = [
        (1, 'Low'),
        (2, 'Medium'),
        (3, 'High'),
        (4, 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Notification content
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default='info'
    )
    
    # Context and links
    context_data = models.JSONField(default=dict, blank=True)
    action_url = models.URLField(blank=True, null=True)
    action_text = models.CharField(max_length=100, blank=True, null=True)
    
    # Delivery settings
    channels = models.CharField(
        max_length=20,
        choices=NOTIFICATION_CHANNELS,
        default='in_app'
    )
    priority = models.IntegerField(
        choices=PRIORITY_LEVELS,
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    
    # Scheduling
    scheduled_for = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    
    # Status tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    is_sent = models.BooleanField(default=False)
    send_attempts = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
            models.Index(fields=['scheduled_for', 'is_sent']),
            models.Index(fields=['notification_type', 'priority']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.email}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at', 'updated_at'])
    
    def mark_as_sent(self):
        """Mark notification as sent"""
        self.is_sent = True
        self.sent_at = timezone.now()
        self.save(update_fields=['is_sent', 'sent_at', 'updated_at'])
    
    def record_attempt(self, error=None):
        """Record a send attempt"""
        self.send_attempts += 1
        self.last_attempt_at = timezone.now()
        if error:
            self.error_message = str(error)[:500]
        self.save(update_fields=[
            'send_attempts', 'last_attempt_at', 'error_message', 'updated_at'
        ])


class NotificationPreference(models.Model):
    """
    User preferences for notifications.
    """
    NOTIFICATION_CATEGORIES = [
        ('order_updates', 'Order Updates'),
        ('messages', 'Messages'),
        ('deadlines', 'Deadline Warnings'),
        ('payments', 'Payment Notifications'),
        ('system', 'System Announcements'),
        ('marketing', 'Marketing Emails'),
        ('writer_updates', 'Writer Application Updates'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Channel preferences
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    
    # Category preferences
    preferences = models.JSONField(
        default=dict,
        help_text="Category-specific preferences"
    )
    
    # Quiet hours
    quiet_hours_start = models.TimeField(blank=True, null=True)
    quiet_hours_end = models.TimeField(blank=True, null=True)
    quiet_hours_enabled = models.BooleanField(default=False)
    
    # Rate limiting
    daily_email_limit = models.IntegerField(default=20)
    emails_sent_today = models.IntegerField(default=0)
    last_reset_date = models.DateField(default=timezone.now)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.email}"
    
    def is_channel_enabled(self, channel: str) -> bool:
        """Check if a specific channel is enabled"""
        channel_map = {
            'email': self.email_enabled,
            'push': self.push_enabled,
            'sms': self.sms_enabled,
        }
        return channel_map.get(channel, False)
    
    def is_category_enabled(self, category: str, channel: str) -> bool:
        """Check if a category is enabled for a specific channel"""
        if not self.is_channel_enabled(channel):
            return False
        
        # Check category preferences
        category_prefs = self.preferences.get(category, {})
        return category_prefs.get(channel, True)
    
    def in_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours"""
        if not self.quiet_hours_enabled or not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        now = timezone.now().time()
        
        if self.quiet_hours_start <= self.quiet_hours_end:
            # Normal case: quiet hours within same day
            return self.quiet_hours_start <= now <= self.quiet_hours_end
        else:
            # Quiet hours span midnight
            return now >= self.quiet_hours_start or now <= self.quiet_hours_end
    
    def can_send_email(self) -> bool:
        """Check if user can receive another email today"""
        self._reset_daily_counter_if_needed()
        return self.emails_sent_today < self.daily_email_limit
    
    def increment_email_count(self):
        """Increment email counter"""
        self._reset_daily_counter_if_needed()
        self.emails_sent_today += 1
        self.save(update_fields=['emails_sent_today', 'updated_at'])
    
    def _reset_daily_counter_if_needed(self):
        """Reset daily counter if it's a new day"""
        today = timezone.now().date()
        if self.last_reset_date < today:
            self.emails_sent_today = 0
            self.last_reset_date = today
            self.save(update_fields=['emails_sent_today', 'last_reset_date', 'updated_at'])


class EmailTemplate(models.Model):
    """
    Reusable email templates for notifications.
    """
    TEMPLATE_TYPES = [
        ('order_update', 'Order Update'),
        ('payment', 'Payment Notification'),
        ('deadline', 'Deadline Warning'),
        ('message', 'New Message'),
        ('system', 'System Notification'),
        ('writer', 'Writer Application'),
        ('security', 'Security Alert'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES)
    subject = models.CharField(max_length=255)
    body_template = models.TextField(help_text="HTML template with placeholders")
    plain_text_template = models.TextField(help_text="Plain text version")
    
    # Placeholder documentation
    placeholders = models.JSONField(
        default=list,
        help_text="List of available placeholders with descriptions"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Email Template'
        verbose_name_plural = 'Email Templates'
        indexes = [
            models.Index(fields=['template_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} (v{self.version})"


class NotificationLog(models.Model):
    """
    Audit log for all notifications sent.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification,
        on_delete=models.SET_NULL,
        null=True,
        related_name='logs'
    )
    
    # Recipient info
    recipient_email = models.EmailField()
    recipient_id = models.UUIDField(null=True, blank=True)
    
    # Delivery info
    channel = models.CharField(max_length=20, choices=Notification.NOTIFICATION_CHANNELS)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('failed', 'Failed'),
            ('bounced', 'Bounced'),
            ('complained', 'Complained'),
        ],
        default='pending'
    )
    
    # Content snapshot
    subject = models.CharField(max_length=255, blank=True, null=True)
    message_preview = models.TextField(blank=True, null=True)
    
    # Provider info
    provider = models.CharField(max_length=100, blank=True, null=True)
    provider_message_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Timing
    sent_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    opened_at = models.DateTimeField(blank=True, null=True)
    clicked_at = models.DateTimeField(blank=True, null=True)
    
    # Error tracking
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification Log'
        verbose_name_plural = 'Notification Logs'
        indexes = [
            models.Index(fields=['recipient_email', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['channel', 'created_at']),
            models.Index(fields=['provider_message_id']),
        ]
    
    def __str__(self):
        return f"{self.channel} to {self.recipient_email} - {self.status}"