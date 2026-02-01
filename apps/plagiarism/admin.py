"""
Admin configuration for plagiarism detection.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone

from .models import PlagiarismCheck, PlagiarismReport, PlagiarismPolicy


@admin.register(PlagiarismCheck)
class PlagiarismCheckAdmin(admin.ModelAdmin):
    """Admin interface for plagiarism checks."""
    list_display = [
        'id', 'order_link', 'source', 'status', 'similarity_score_display', 
        'risk_level_display', 'requested_at', 'is_completed'
    ]
    list_filter = ['status', 'source', 'requested_at', 'similarity_score']
    search_fields = [
        'order__order_number', 
        'checked_file__original_filename',
        'raw_result'
    ]
    readonly_fields = [
        'id', 'requested_at', 'started_at', 'completed_at', 
        'is_completed', 'risk_level', 'formatted_result'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'order', 'source', 'status')
        }),
        ('Results', {
            'fields': (
                'similarity_score', 'risk_level', 'word_count', 
                'character_count', 'formatted_result'
            )
        }),
        ('Files', {
            'fields': ('checked_file',)
        }),
        ('Detailed Data', {
            'fields': ('raw_result', 'highlights', 'sources'),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': ('is_sensitive',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('requested_at', 'started_at', 'completed_at')
        }),
        ('Audit', {
            'fields': ('requested_by', 'processed_by')
        }),
    )
    
    def order_link(self, obj):
        """Create clickable link to order."""
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = "Order"
    
    def similarity_score_display(self, obj):
        """Format similarity score with color coding."""
        if not obj.similarity_score:
            return "N/A"
        
        score = obj.similarity_score
        if score < 10:
            color = 'green'
        elif score < 25:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, 
            round(score, 2)
        )
    similarity_score_display.short_description = "Score"
    
    def risk_level_display(self, obj):
        """Display risk level with color coding."""
        risk_level = obj.risk_level
        colors = {
            'low': 'green',
            'medium': 'orange',
            'high': 'red',
            'critical': 'darkred',
            'unknown': 'gray'
        }
        
        color = colors.get(risk_level, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, 
            risk_level.upper()
        )
    risk_level_display.short_description = "Risk Level"
    
    def is_completed(self, obj):
        """Display completion status."""
        return obj.is_completed
    is_completed.boolean = True
    is_completed.short_description = "Completed"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'order', 'checked_file', 'requested_by', 'processed_by'
        )


@admin.register(PlagiarismReport)
class PlagiarismReportAdmin(admin.ModelAdmin):
    """Admin interface for plagiarism reports."""
    list_display = [
        'id', 'check_link', 'title', 'view_count', 'last_viewed', 
        'is_expired_display', 'generated_at'
    ]
    list_filter = ['generated_at', 'expires_at']
    search_fields = ['title', 'access_key', 'summary']
    readonly_fields = [
        'id', 'access_key', 'generated_at', 'view_count', 
        'last_viewed', 'last_viewed_by', 'is_expired'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'plagiarism_check', 'title', 'summary')
        }),
        ('Access Control', {
            'fields': ('access_key', 'is_encrypted', 'view_count', 'last_viewed', 'last_viewed_by')
        }),
        ('Report Content', {
            'fields': ('detailed_analysis',),
            'classes': ('collapse',)
        }),
        ('Expiry', {
            'fields': ('expires_at', 'is_expired')
        }),
        ('Timestamps', {
            'fields': ('generated_at',)
        }),
    )
    
    def check_link(self, obj):
        """Create clickable link to plagiarism check."""
        url = reverse('admin:plagiarism_plagiarismcheck_change', args=[obj.plagiarism_check.id])
        return format_html('<a href="{}">Check {}</a>', url, obj.plagiarism_check.id[:8])
    check_link.short_description = "Plagiarism Check"
    
    def is_expired_display(self, obj):
        """Display expired status."""
        if obj.is_expired:
            return format_html(
                '<span style="color: red; font-weight: bold;">EXPIRED</span>'
            )
        return "No"
    is_expired_display.short_description = "Expired"
    
    def has_add_permission(self, request):
        """Prevent manual addition of reports."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Allow changes only to certain fields."""
        if obj:
            # Only allow changes to non-critical fields
            return request.user.is_superuser
        return True


@admin.register(PlagiarismPolicy)
class PlagiarismPolicyAdmin(admin.ModelAdmin):
    """Admin interface for plagiarism policies."""
    list_display = ['name', 'is_active', 'warning_threshold', 'action_threshold', 'rejection_threshold', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Thresholds', {
            'fields': ('warning_threshold', 'action_threshold', 'rejection_threshold')
        }),
        ('Actions', {
            'fields': ('warning_action', 'critical_action')
        }),
        ('Scope', {
            'fields': ('order_types', 'client_tiers')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Validate thresholds on save."""
        if obj.warning_threshold >= obj.action_threshold:
            from django.contrib import messages
            messages.error(request, "Warning threshold must be less than action threshold")
            return
        
        if obj.action_threshold >= obj.rejection_threshold:
            from django.contrib import messages
            messages.error(request, "Action threshold must be less than rejection threshold")
            return
        
        super().save_model(request, obj, form, change)