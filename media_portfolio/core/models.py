from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    """
    Abstract base model with common fields for all models
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0, help_text="Order for display")

    class Meta:
        abstract = True
        ordering = ['sort_order', '-created_at']


class SiteSettings(models.Model):
    """
    Global site settings
    """
    site_title = models.CharField(max_length=200, default="Media Portfolio")
    site_description = models.TextField(blank=True)
    
    # Contact info
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    # Social media links
    instagram_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    behance_url = models.URLField(blank=True)
    
    # SEO
    meta_keywords = models.CharField(max_length=500, blank=True)
    meta_description = models.TextField(blank=True)
    google_analytics_id = models.CharField(max_length=50, blank=True)
    
    # Logo and favicon
    logo = models.ImageField(upload_to='site/', blank=True, null=True)
    favicon = models.ImageField(upload_to='site/', blank=True, null=True)
    
    # Legal
    copyright_text = models.CharField(max_length=200, default="© All Rights Reserved")
    privacy_policy = models.TextField(blank=True)
    terms_of_service = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return self.site_title

    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and SiteSettings.objects.exists():
            return
        super().save(*args, **kwargs)