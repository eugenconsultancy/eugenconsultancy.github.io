from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.utils.html import format_html
from .models import Project, ProjectLike, ProjectComment


class ProjectLikeInline(admin.TabularInline):
    model = ProjectLike
    extra = 0
    readonly_fields = ['session_key', 'ip_address', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


class ProjectCommentInline(admin.TabularInline):
    model = ProjectComment
    extra = 0
    readonly_fields = ['name', 'email', 'content', 'created_at']
    fields = ['name', 'content', 'is_approved', 'created_at']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'difficulty_level', 'is_featured', 'is_published',
        'stars_count', 'view_count', 'thumbnail_preview'
    ]
    list_filter = [
        'difficulty_level', 'is_featured', 'is_published', 'license',
        'categories', 'created_at'
    ]
    search_fields = ['title', 'short_summary', 'description', 'tags']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = [
        'stars_count', 'forks_count', 'last_github_sync', 'view_count',
        'thumbnail_preview', 'thumbnail_webp_preview', 'thumbnail_blur_preview'
    ]
    inlines = [ProjectLikeInline, ProjectCommentInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'title', 'slug', 'short_summary', 'description',
                'difficulty_level', 'is_featured', 'performance_score'
            )
        }),
        ('Project Details', {
            'fields': ('problem_statement', 'solution'),
            'classes': ('wide',)
        }),
        ('Technical Stack', {
            'fields': ('technical_stack', 'api_integrations', 'tags'),
            'classes': ('wide',)
        }),
        ('Media', {
            'fields': (
                'thumbnail', 'thumbnail_preview',
                'thumbnail_webp', 'thumbnail_webp_preview',
                'thumbnail_blur', 'thumbnail_blur_preview'
            )
        }),
        ('Links', {
            'fields': ('github_url', 'live_demo_url', 'documentation_url')
        }),
        ('Organization', {
            'fields': ('categories', 'is_published', 'published_date', 'sort_order')
        }),
        ('GitHub Stats', {
            'fields': ('stars_count', 'forks_count', 'last_github_sync'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('view_count',),
            'classes': ('collapse',)
        }),
        ('Copyright', {
            'fields': ('copyright_notice', 'license')
        }),
    )
    
    actions = ['mark_as_featured', 'mark_as_not_featured']
    
    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 100px;" />',
                obj.thumbnail.url
            )
        return "No thumbnail"
    thumbnail_preview.short_description = 'Thumbnail Preview'
    
    def thumbnail_webp_preview(self, obj):
        if obj.thumbnail_webp:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 100px;" />',
                obj.thumbnail_webp.url
            )
        return "Not generated"
    thumbnail_webp_preview.short_description = 'WebP Preview'
    
    def thumbnail_blur_preview(self, obj):
        if obj.thumbnail_blur:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 100px;" />',
                obj.thumbnail_blur.url
            )
        return "Not generated"
    thumbnail_blur_preview.short_description = 'Blur Preview'
    
    def mark_as_featured(self, request, queryset):
        queryset.update(is_featured=True)
    mark_as_featured.short_description = "Mark selected as featured"
    
    def mark_as_not_featured(self, request, queryset):
        queryset.update(is_featured=False)
    mark_as_not_featured.short_description = "Mark selected as not featured"


@admin.register(ProjectComment)
class ProjectCommentAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'project', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'is_spam', 'created_at']
    search_fields = ['name', 'email', 'content']
    readonly_fields = ['ip_address', 'user_agent', 'created_at']
    
    actions = ['approve_comments', 'mark_as_spam']
    
    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
    approve_comments.short_description = "Approve selected comments"
    
    def mark_as_spam(self, request, queryset):
        queryset.update(is_spam=True, is_approved=False)
    mark_as_spam.short_description = "Mark selected as spam"


@admin.register(ProjectLike)
class ProjectLikeAdmin(admin.ModelAdmin):
    list_display = ['project', 'session_key', 'ip_address', 'created_at']
    list_filter = ['created_at']
    search_fields = ['project__title', 'session_key', 'ip_address']
    readonly_fields = ['project', 'session_key', 'ip_address', 'user_agent', 'created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False