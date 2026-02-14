from django.contrib import admin
from .models import GitHubRepo, GitHubSyncLog


@admin.register(GitHubRepo)
class GitHubRepoAdmin(admin.ModelAdmin):
    list_display = ['name', 'primary_language', 'stars_count', 'forks_count', 'last_synced']
    list_filter = ['primary_language', 'last_synced']
    search_fields = ['name', 'full_name', 'description']
    readonly_fields = ['full_name', 'html_url', 'clone_url', 'created_at_github', 'last_synced']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'full_name', 'description')
        }),
        ('URLs', {
            'fields': ('html_url', 'clone_url', 'homepage')
        }),
        ('Statistics', {
            'fields': ('stars_count', 'forks_count', 'watchers_count', 'open_issues_count')
        }),
        ('Languages', {
            'fields': ('primary_language', 'languages')
        }),
        ('Dates', {
            'fields': ('created_at_github', 'updated_at_github', 'pushed_at_github', 'last_synced')
        }),
    )
    
    def has_add_permission(self, request):
        return False


@admin.register(GitHubSyncLog)
class GitHubSyncLogAdmin(admin.ModelAdmin):
    list_display = ['synced_at', 'repos_created', 'repos_updated', 'status']
    list_filter = ['status', 'synced_at']
    readonly_fields = ['synced_at', 'repos_created', 'repos_updated', 'status', 'error_message']
    
    def has_add_permission(self, request):
        return False