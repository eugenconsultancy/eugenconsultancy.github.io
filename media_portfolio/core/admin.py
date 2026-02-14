from django.contrib import admin
from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Basic Info', {
            'fields': ('site_title', 'site_description')
        }),
        ('Contact', {
            'fields': ('contact_email', 'contact_phone')
        }),
        ('Social Media', {
            'fields': ('instagram_url', 'twitter_url', 'facebook_url', 
                      'linkedin_url', 'github_url', 'behance_url')
        }),
        ('SEO', {
            'fields': ('meta_keywords', 'meta_description', 'google_analytics_id')
        }),
        ('Branding', {
            'fields': ('logo', 'favicon')
        }),
        ('Legal', {
            'fields': ('copyright_text', 'privacy_policy', 'terms_of_service')
        }),
    )
    
    def has_add_permission(self, request):
        # Prevent adding multiple settings
        return not SiteSettings.objects.exists()