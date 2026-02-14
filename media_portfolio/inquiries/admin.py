from django.contrib import admin
from django.utils import timezone
from .models import Inquiry


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'inquiry_type', 'subject', 'status', 'created_at']
    list_filter = ['inquiry_type', 'status', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    readonly_fields = ['ip_address', 'created_at', 'responded_at']
    
    fieldsets = (
        ('Inquiry Details', {
            'fields': ('inquiry_type', 'media_item', 'subject', 'message')
        }),
        ('Contact Information', {
            'fields': ('name', 'email', 'phone', 'company')
        }),
        ('Additional Information', {
            'fields': ('usage_type', 'deadline', 'budget_range'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('status', 'responded_at', 'response_notes')
        }),
        ('Legal', {
            'fields': ('accepted_terms', 'accepted_privacy')
        }),
        ('Technical', {
            'fields': ('ip_address', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_read', 'mark_as_replied', 'mark_as_archived']
    
    def mark_as_read(self, request, queryset):
        queryset.update(status='read')
    mark_as_read.short_description = "Mark selected as read"
    
    def mark_as_replied(self, request, queryset):
        queryset.update(status='replied', responded_at=timezone.now())
    mark_as_replied.short_description = "Mark selected as replied"
    
    def mark_as_archived(self, request, queryset):
        queryset.update(status='archived')
    mark_as_archived.short_description = "Archive selected"