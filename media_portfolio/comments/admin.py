from django.contrib import admin
from .models import Comment, Testimonial


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'media_item', 'is_approved', 'is_featured', 'created_at']
    list_filter = ['is_approved', 'is_spam', 'is_featured', 'created_at']
    search_fields = ['name', 'email', 'content']
    readonly_fields = ['ip_address', 'user_agent', 'created_at', 'updated_at']  # Added updated_at here
    
    fieldsets = (
        ('Comment', {
            'fields': ('media_item', 'parent', 'name', 'email', 'website', 'content')
        }),
        ('Moderation', {
            'fields': ('is_approved', 'is_spam', 'is_featured', 'can_use_as_testimonial', 'testimonial_approved')
        }),
        ('Technical', {
            'fields': ('ip_address', 'user_agent', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_comments', 'mark_as_spam', 'feature_comments']
    
    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
    approve_comments.short_description = "Approve selected comments"
    
    def mark_as_spam(self, request, queryset):
        queryset.update(is_spam=True, is_approved=False)
    mark_as_spam.short_description = "Mark selected as spam"
    
    def feature_comments(self, request, queryset):
        queryset.update(is_featured=True)
    feature_comments.short_description = "Feature selected comments"


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'rating', 'featured', 'created_at']
    list_filter = ['rating', 'featured']
    search_fields = ['name', 'company', 'content']
    
    fieldsets = (
        ('Testimonial', {
            'fields': ('name', 'title', 'company', 'content', 'rating')
        }),
        ('Source', {
            'fields': ('source_comment', 'photo')
        }),
        ('Display', {
            'fields': ('featured', 'sort_order')
        }),
    )