# apps/notifications/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from apps.notifications.models import (
    Notification, NotificationPreference, EmailTemplate, NotificationLog
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'title_preview', 'recipient_email', 'notification_type',
        'channels', 'priority', 'is_sent', 'is_read', 'created_at'
    ]
    list_filter = [
        'notification_type', 'channels', 'priority',
        'is_sent', 'is_read', 'created_at'
    ]
    search_fields = ['title', 'message', 'user__email']
    readonly_fields = [
        'created_at', 'updated_at', 'sent_at', 'read_at',
        'send_attempts', 'last_attempt_at', 'error_message'
    ]
    list_select_related = ['user']
    date_hierarchy = 'created_at'
    actions = ['mark_as_sent', 'retry_sending']
    
    def title_preview(self, obj):
        if len(obj.title) > 50:
            return obj.title[:50] + '...'
        return obj.title
    title_preview.short_description = 'Title'
    
    def recipient_email(self, obj):
        return obj.user.email
    recipient_email.short_description = 'Recipient'
    
    def mark_as_sent(self, request, queryset):
        for notification in queryset:
            notification.mark_as_sent()
        self.message_user(request, f'{queryset.count()} notifications marked as sent.')
    mark_as_sent.short_description = 'Mark selected as sent'
    
    def retry_sending(self, request, queryset):
        from apps.notifications.tasks import deliver_notification
        for notification in queryset:
            deliver_notification.delay(str(notification.id))
        self.message_user(request, f'{queryset.count()} notifications queued for retry.')
    retry_sending.short_description = 'Retry sending selected'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'email_enabled', 'push_enabled',
        'sms_enabled', 'quiet_hours_enabled', 'updated_at'
    ]
    list_filter = ['email_enabled', 'push_enabled', 'sms_enabled', 'quiet_hours_enabled']
    search_fields = ['user__email']
    readonly_fields = ['updated_at']
    list_select_related = ['user']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'template_type', 'subject_preview',
        'version', 'is_active', 'updated_at'
    ]
    list_filter = ['template_type', 'is_active', 'version']
    search_fields = ['name', 'subject', 'body_template']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_active']
    actions = ['duplicate_templates']
    
    def subject_preview(self, obj):
        if len(obj.subject) > 50:
            return obj.subject[:50] + '...'
        return obj.subject
    subject_preview.short_description = 'Subject'
    
    def duplicate_templates(self, request, queryset):
        for template in queryset:
            new_template = EmailTemplate.objects.create(
                name=f"{template.name} (Copy)",
                template_type=template.template_type,
                subject=template.subject,
                body_template=template.body_template,
                plain_text_template=template.plain_text_template,
                placeholders=template.placeholders,
                version=1,
                is_active=False
            )
        self.message_user(request, f'{queryset.count()} templates duplicated.')
    duplicate_templates.short_description = 'Duplicate selected templates'


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = [
        'recipient_email', 'channel', 'status',
        'subject_preview', 'sent_at', 'delivered_at'
    ]
    list_filter = ['channel', 'status', 'sent_at']
    search_fields = ['recipient_email', 'subject', 'provider_message_id']
    readonly_fields = ['created_at', 'sent_at', 'delivered_at', 'opened_at', 'clicked_at']
    date_hierarchy = 'created_at'
    
    def subject_preview(self, obj):
        if obj.subject and len(obj.subject) > 50:
            return obj.subject[:50] + '...'
        return obj.subject or 'No subject'
    subject_preview.short_description = 'Subject'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('notification')