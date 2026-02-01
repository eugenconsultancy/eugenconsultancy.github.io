# apps/messaging/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse

from apps.messaging.models import Conversation, Message, MessageAttachment


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = [
        'order_id', 'client_email', 'writer_email', 'message_count',
        'created_at', 'updated_at', 'is_closed', 'view_messages_link'
    ]
    list_filter = ['is_closed', 'created_at', 'updated_at']
    search_fields = [
        'order__order_id',
        'order__client__email',
        'order__assigned_writer__email'
    ]
    readonly_fields = ['created_at', 'updated_at']
    actions = ['close_conversations', 'open_conversations']
    
    def order_id(self, obj):
        return obj.order.order_id
    order_id.short_description = 'Order ID'
    
    def client_email(self, obj):
        return obj.order.client.email
    client_email.short_description = 'Client'
    
    def writer_email(self, obj):
        if obj.order.assigned_writer:
            return obj.order.assigned_writer.email
        return 'Not assigned'
    writer_email.short_description = 'Writer'
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'
    
    def view_messages_link(self, obj):
        url = reverse('admin:messaging_message_changelist') + f'?conversation__id__exact={obj.id}'
        return format_html('<a href="{}">View Messages</a>', url)
    view_messages_link.short_description = 'Messages'
    
    def close_conversations(self, request, queryset):
        updated = queryset.update(is_closed=True)
        self.message_user(request, f'{updated} conversations closed.')
    close_conversations.short_description = 'Close selected conversations'
    
    def open_conversations(self, request, queryset):
        updated = queryset.update(is_closed=False)
        self.message_user(request, f'{updated} conversations opened.')
    open_conversations.short_description = 'Open selected conversations'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        'truncated_content', 'sender_email', 'conversation_order',
        'is_system_message', 'is_read', 'admin_has_viewed', 'created_at'
    ]
    list_filter = [
        'is_system_message', 'is_read', 'admin_has_viewed',
        'created_at', 'sender__is_staff'
    ]
    search_fields = ['content', 'sender__email', 'conversation__order__order_id']
    readonly_fields = ['created_at', 'updated_at', 'read_at', 'admin_viewed_at']
    date_hierarchy = 'created_at'
    
    def truncated_content(self, obj):
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    truncated_content.short_description = 'Content'
    
    def sender_email(self, obj):
        if obj.sender:
            return obj.sender.email
        return 'System'
    sender_email.short_description = 'Sender'
    
    def conversation_order(self, obj):
        return obj.conversation.order.order_id
    conversation_order.short_description = 'Order ID'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('sender', 'conversation__order')


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = [
        'original_filename', 'file_type', 'file_size_mb',
        'virus_scan_status', 'scanned_at', 'created_at', 'download_link'
    ]
    list_filter = ['virus_scan_status', 'file_type', 'created_at']
    search_fields = ['original_filename', 'file_hash']
    readonly_fields = [
        'original_filename', 'file_size', 'file_type',
        'file_hash', 'virus_scan_status', 'virus_scan_result',
        'scanned_at', 'created_at'
    ]
    actions = ['rescan_for_viruses']
    
    def file_size_mb(self, obj):
        return f"{obj.file_size / 1024 / 1024:.2f} MB"
    file_size_mb.short_description = 'Size'
    
    def download_link(self, obj):
        if obj.virus_scan_status == 'clean':
            return format_html('<a href="{}" target="_blank">Download</a>', obj.file.url)
        return 'Not available'
    download_link.short_description = 'Download'
    
    def rescan_for_viruses(self, request, queryset):
        from apps.messaging.tasks import scan_attachment_for_viruses
        for attachment in queryset:
            scan_attachment_for_viruses.delay(str(attachment.id))
        self.message_user(request, f'{queryset.count()} attachments queued for rescan.')
    rescan_for_viruses.short_description = 'Rescan selected files for viruses'