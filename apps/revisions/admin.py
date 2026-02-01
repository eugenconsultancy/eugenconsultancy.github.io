# apps/revisions/admin.py
"""
Admin configuration for revision management.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Avg

from .models import RevisionRequest, RevisionCycle, RevisionAuditLog


class RevisionRequestInline(admin.TabularInline):
    """Inline display for revision requests in order admin."""
    model = RevisionRequest
    extra = 0
    fields = ['title', 'status', 'deadline', 'revisions_used', 'is_overdue']
    readonly_fields = ['is_overdue']
    show_change_link = True
    
    def is_overdue(self, obj):
        """Display overdue status."""
        if obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ OVERDUE</span>'
            )
        return "No"
    is_overdue.short_description = "Overdue"


@admin.register(RevisionRequest)
class RevisionRequestAdmin(admin.ModelAdmin):
    """Admin interface for revision requests."""
    list_display = [
        'id', 'order_link', 'client', 'writer', 'status', 
        'deadline', 'is_overdue_display', 'revisions_used'
    ]
    list_filter = ['status', 'deadline', 'requested_at']
    search_fields = [
        'order__order_number', 
        'client__email', 
        'writer__email',
        'title'
    ]
    readonly_fields = [
        'id', 'get_created_at', 'get_last_modified', 
        'revisions_remaining', 'is_overdue'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'order', 'client', 'writer', 'title', 'instructions')
        }),
        ('Revision Details', {
            'fields': (
                'status', 'deadline', 'max_revisions_allowed', 
                'revisions_used', 'revisions_remaining'
            )
        }),
        ('Timing', {
            'fields': ('requested_at', 'started_at', 'completed_at', 'is_overdue')
        }),
        ('Files', {
            'fields': ('original_files', 'revised_files')
        }),
        ('Audit', {
            'fields': ('created_by', 'get_last_modified')
        }),
    )
    
    def order_link(self, obj):
        """Create clickable link to order."""
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = "Order"
    
    def is_overdue_display(self, obj):
        """Display overdue status in list."""
        if obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠ OVERDUE</span>'
            )
        return "No"
    is_overdue_display.short_description = "Overdue"
    
    def get_created_at(self, obj):
        """Get created_at as a method."""
        return obj.created_at
    get_created_at.short_description = 'Created At'
    
    def get_last_modified(self, obj):
        """Get last_modified as a method."""
        return obj.last_modified
    get_last_modified.short_description = 'Last Modified'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'order', 'client', 'writer', 'created_by'
    )


@admin.register(RevisionCycle)
class RevisionCycleAdmin(admin.ModelAdmin):
    """Admin interface for revision cycles."""
    list_display = [
        'id', 'order_link', 'max_revisions_allowed', 
        'revisions_used', 'revisions_remaining', 'is_active', 'is_expired'
    ]
    list_filter = ['is_active', 'started_at', 'ends_at']
    search_fields = ['order__order_number']
    readonly_fields = ['id', 'is_expired', 'revisions_remaining']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'order', 'is_active')
        }),
        ('Revision Limits', {
            'fields': ('max_revisions_allowed', 'revisions_used', 'revisions_remaining')
        }),
        ('Timing', {
            'fields': ('revision_period_days', 'started_at', 'ends_at', 'is_expired')
        }),
        ('Requests', {
            'fields': ('revision_requests',)
        }),
    )
    
    def order_link(self, obj):
        """Create clickable link to order."""
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = "Order"
    
    def is_expired(self, obj):
        """Display expired status."""
        if obj.is_expired:
            return format_html(
                '<span style="color: orange; font-weight: bold;">EXPIRED</span>'
            )
        return "No"
    is_expired.short_description = "Expired"


@admin.register(RevisionAuditLog)
class RevisionAuditLogAdmin(admin.ModelAdmin):
    """Admin interface for revision audit logs."""
    list_display = ['id', 'revision_link', 'action', 'performed_by', 'performed_at']
    list_filter = ['action', 'performed_at']
    search_fields = [
        'revision__order__order_number',
        'performed_by__email',
        'details'
    ]
    # FIXED: Changed from field name to method name
    readonly_fields = ['id', 'get_performed_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'revision', 'action', 'details')
        }),
        ('Actor', {
            'fields': ('performed_by', 'ip_address', 'user_agent')
        }),
        ('Timestamp', {
            'fields': ('get_performed_at',)
        }),
    )
    
    def revision_link(self, obj):
        """Create clickable link to revision."""
        url = reverse('admin:revisions_revisionrequest_change', args=[obj.revision.id])
        return format_html('<a href="{}">Revision {}</a>', url, obj.revision.id[:8])
    revision_link.short_description = "Revision"
    
    def get_performed_at(self, obj):
        """Get performed_at as a method."""
        return obj.performed_at
    get_performed_at.short_description = 'Performed At'
    
    def has_add_permission(self, request):
        """Prevent manual addition of audit logs."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of audit logs."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of audit logs."""
        return False