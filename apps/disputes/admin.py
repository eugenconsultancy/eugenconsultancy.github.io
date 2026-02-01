"""
Admin configuration for dispute resolution.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone

from .models import Dispute, DisputeEvidence, DisputeMessage, DisputeResolutionLog


class DisputeEvidenceInline(admin.TabularInline):
    """Inline display for dispute evidence."""
    model = DisputeEvidence
    extra = 0
    fields = ['evidence_type', 'title', 'submitted_by', 'submitted_at', 'is_verified']
    readonly_fields = ['submitted_at']
    show_change_link = True


class DisputeMessageInline(admin.TabularInline):
    """Inline display for dispute messages."""
    model = DisputeMessage
    extra = 0
    fields = ['message_type', 'sent_by', 'content_short', 'sent_at']
    readonly_fields = ['content_short', 'sent_at']
    show_change_link = True
    
    def content_short(self, obj):
        """Shorten message content for display."""
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_short.short_description = "Content"


class DisputeResolutionLogInline(admin.TabularInline):
    """Inline display for resolution logs."""
    model = DisputeResolutionLog
    extra = 0
    fields = ['action', 'performed_by', 'performed_at']
    readonly_fields = ['performed_at']
    show_change_link = True


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    """Admin interface for disputes."""
    list_display = [
        'id_short', 'order_link', 'opened_by', 'against_user', 'reason', 
        'status_display', 'priority_display', 'sla_status_display', 'opened_at'
    ]
    list_filter = ['status', 'reason', 'priority', 'opened_at']
    search_fields = [
        'order__order_number', 
        'opened_by__email', 
        'against_user__email',
        'title',
        'description'
    ]
    readonly_fields = [
        'id', 'opened_at', 'under_review_at', 'resolved_at', 
        'is_overdue', 'sla_status'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'order', 'opened_by', 'against_user')
        }),
        ('Dispute Details', {
            'fields': ('reason', 'title', 'description', 'priority')
        }),
        ('Resolution', {
            'fields': ('status', 'resolution_type', 'resolution_details', 'resolution_proposed_by')
        }),
        ('Financial', {
            'fields': ('requested_refund_amount', 'approved_refund_amount')
        }),
        ('SLA & Timing', {
            'fields': (
                'opened_at', 'under_review_at', 'resolved_at',
                'sla_deadline', 'first_response_at', 'is_overdue', 'sla_status'
            )
        }),
        ('Admin Assignment', {
            'fields': ('assigned_to',)
        }),
        ('Snapshots', {
            'fields': ('order_snapshot', 'messages_snapshot', 'files_snapshot'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [DisputeEvidenceInline, DisputeMessageInline, DisputeResolutionLogInline]
    
    def id_short(self, obj):
        """Display shortened dispute ID."""
        return obj.id.hex[:8]
    id_short.short_description = "Dispute ID"
    
    def order_link(self, obj):
        """Create clickable link to order."""
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = "Order"
    
    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            'opened': 'orange',
            'under_review': 'blue',
            'awaiting_response': 'purple',
            'evidence_review': 'teal',
            'resolution_proposed': 'green',
            'resolved': 'darkgreen',
            'escalated': 'red',
            'cancelled': 'gray'
        }
        
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, 
            obj.get_status_display()
        )
    status_display.short_description = "Status"
    
    def priority_display(self, obj):
        """Display priority with color coding."""
        colors = {
            'low': 'green',
            'medium': 'orange',
            'high': 'red',
            'critical': 'darkred'
        }
        
        color = colors.get(obj.priority, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, 
            obj.get_priority_display().upper()
        )
    priority_display.short_description = "Priority"
    
    def sla_status_display(self, obj):
        """Display SLA status with color coding."""
        sla_status = obj.sla_status
        colors = {
            'not_set': 'gray',
            'ok': 'green',
            'warning': 'orange',
            'urgent': 'red',
            'overdue': 'darkred'
        }
        
        color = colors.get(sla_status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, 
            sla_status.upper()
        )
    sla_status_display.short_description = "SLA Status"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'order', 'opened_by', 'against_user', 'assigned_to', 'resolution_proposed_by'
        )
    
    actions = ['mark_as_resolved', 'escalate_dispute', 'assign_to_me']
    
    def mark_as_resolved(self, request, queryset):
        """Admin action to mark disputes as resolved."""
        for dispute in queryset:
            dispute.status = 'resolved'
            dispute.resolved_at = timezone.now()
            dispute.save()
        
        self.message_user(request, f"{queryset.count()} disputes marked as resolved.")
    mark_as_resolved.short_description = "Mark selected disputes as resolved"
    
    def escalate_dispute(self, request, queryset):
        """Admin action to escalate disputes."""
        for dispute in queryset:
            dispute.escalate()
            dispute.save()
        
        self.message_user(request, f"{queryset.count()} disputes escalated.")
    escalate_dispute.short_description = "Escalate selected disputes"
    
    def assign_to_me(self, request, queryset):
        """Admin action to assign disputes to current user."""
        for dispute in queryset:
            dispute.assign_for_review(request.user)
            dispute.save()
        
        self.message_user(request, f"{queryset.count()} disputes assigned to you.")
    assign_to_me.short_description = "Assign selected disputes to me"


@admin.register(DisputeEvidence)
class DisputeEvidenceAdmin(admin.ModelAdmin):
    """Admin interface for dispute evidence."""
    list_display = ['id_short', 'dispute_link', 'evidence_type', 'title', 'submitted_by', 'submitted_at', 'is_verified']
    list_filter = ['evidence_type', 'is_verified', 'submitted_at']
    search_fields = ['dispute__id', 'title', 'description', 'content']
    readonly_fields = ['id', 'submitted_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'dispute', 'evidence_type', 'title', 'description')
        }),
        ('Evidence Content', {
            'fields': ('file', 'content')
        }),
        ('Submission', {
            'fields': ('submitted_by', 'submitted_at')
        }),
        ('Verification', {
            'fields': ('is_verified', 'verified_by', 'verified_at', 'admin_notes')
        }),
    )
    
    def id_short(self, obj):
        """Display shortened evidence ID."""
        return obj.id.hex[:8]
    id_short.short_description = "Evidence ID"
    
    def dispute_link(self, obj):
        """Create clickable link to dispute."""
        url = reverse('admin:disputes_dispute_change', args=[obj.dispute.id])
        return format_html('<a href="{}">Dispute {}</a>', url, obj.dispute.id.hex[:8])
    dispute_link.short_description = "Dispute"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'dispute', 'submitted_by', 'verified_by', 'file'
        )


@admin.register(DisputeMessage)
class DisputeMessageAdmin(admin.ModelAdmin):
    """Admin interface for dispute messages."""
    list_display = ['id_short', 'dispute_link', 'message_type', 'sent_by', 'content_short', 'sent_at']
    list_filter = ['message_type', 'sent_at']
    search_fields = ['dispute__id', 'content', 'sent_by__email']
    readonly_fields = ['id', 'sent_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'dispute', 'message_type')
        }),
        ('Message Content', {
            'fields': ('content', 'attachments')
        }),
        ('Visibility', {
            'fields': ('visible_to_client', 'visible_to_writer', 'visible_to_admin')
        }),
        ('Sender', {
            'fields': ('sent_by', 'sent_at')
        }),
        ('Read Receipts', {
            'fields': ('read_by',),
            'classes': ('collapse',)
        }),
    )
    
    def id_short(self, obj):
        """Display shortened message ID."""
        return obj.id.hex[:8]
    id_short.short_description = "Message ID"
    
    def dispute_link(self, obj):
        """Create clickable link to dispute."""
        url = reverse('admin:disputes_dispute_change', args=[obj.dispute.id])
        return format_html('<a href="{}">Dispute {}</a>', url, obj.dispute.id.hex[:8])
    dispute_link.short_description = "Dispute"
    
    def content_short(self, obj):
        """Shorten message content for display."""
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_short.short_description = "Content"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('dispute', 'sent_by')


@admin.register(DisputeResolutionLog)
class DisputeResolutionLogAdmin(admin.ModelAdmin):
    """Admin interface for dispute resolution logs."""
    list_display = ['id_short', 'dispute_link', 'action', 'performed_by', 'performed_at']
    list_filter = ['action', 'performed_at']
    search_fields = ['dispute__id', 'details', 'performed_by__email']
    readonly_fields = ['id', 'performed_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'dispute', 'action', 'details')
        }),
        ('Actor', {
            'fields': ('performed_by', 'ip_address', 'user_agent')
        }),
        ('Timestamp', {
            'fields': ('performed_at',)
        }),
    )
    
    def id_short(self, obj):
        """Display shortened log ID."""
        return obj.id.hex[:8]
    id_short.short_description = "Log ID"
    
    def dispute_link(self, obj):
        """Create clickable link to dispute."""
        url = reverse('admin:disputes_dispute_change', args=[obj.dispute.id])
        return format_html('<a href="{}">Dispute {}</a>', url, obj.dispute.id.hex[:8])
    dispute_link.short_description = "Dispute"
    
    def has_add_permission(self, request):
        """Prevent manual addition of logs."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of logs."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of logs."""
        return False