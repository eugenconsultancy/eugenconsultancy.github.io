from django.contrib import admin
from .models import BlogPost, BlogSyncLog


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'source', 'published_at', 'read_time_minutes', 'is_featured', 'is_published']
    list_filter = ['source', 'is_featured', 'is_published', 'published_at']
    search_fields = ['title', 'excerpt', 'author_name']
    readonly_fields = ['external_id', 'external_url', 'reactions_count', 'comments_count']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'source', 'external_id', 'external_url')
        }),
        ('Content', {
            'fields': ('excerpt', 'content', 'cover_image')
        }),
        ('Metadata', {
            'fields': ('author_name', 'published_at', 'read_time_minutes')
        }),
        ('Statistics', {
            'fields': ('reactions_count', 'comments_count'),
            'classes': ('collapse',)
        }),
        ('Display', {
            'fields': ('is_featured', 'is_published', 'sort_order')
        }),
    )
    
    actions = ['mark_as_featured', 'mark_as_not_featured']
    
    def mark_as_featured(self, request, queryset):
        queryset.update(is_featured=True)
    mark_as_featured.short_description = "Mark selected as featured"
    
    def mark_as_not_featured(self, request, queryset):
        queryset.update(is_featured=False)
    mark_as_not_featured.short_description = "Mark selected as not featured"


@admin.register(BlogSyncLog)
class BlogSyncLogAdmin(admin.ModelAdmin):
    list_display = ['source', 'synced_at', 'posts_created', 'posts_updated', 'status']
    list_filter = ['source', 'status', 'synced_at']
    readonly_fields = ['source', 'synced_at', 'posts_created', 'posts_updated', 'status', 'error_message']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False