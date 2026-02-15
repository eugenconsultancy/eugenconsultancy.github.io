from django.db import models
from media_portfolio.core.models import BaseModel


class BlogPost(BaseModel):
    """
    Model for storing blog posts from external sources (Dev.to, Medium)
    """
    SOURCE_CHOICES = [
        ('devto', 'Dev.to'),
        ('medium', 'Medium'),
        ('custom', 'Custom'),
    ]

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, unique=True)
    
    # External source info
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='devto')
    external_id = models.CharField(max_length=100, blank=True, help_text="External post ID")
    external_url = models.URLField()
    
    # Content
    excerpt = models.TextField(help_text="Short excerpt/summary")
    content = models.TextField(blank=True, help_text="Full content (if available)")
    
    # Media
    cover_image = models.URLField(blank=True, help_text="Cover image URL")
    
    # Metadata
    author_name = models.CharField(max_length=100, default="Author")
    published_at = models.DateTimeField()
    
    # Stats
    read_time_minutes = models.IntegerField(default=0)
    reactions_count = models.IntegerField(default=0)
    comments_count = models.IntegerField(default=0)
    
    # Display
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)

    class Meta:
        app_label = 'blog'
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['source', '-published_at']),
            models.Index(fields=['is_featured', '-published_at']),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return self.external_url  # Link to original post


class BlogSyncLog(BaseModel):
    """
    Log for blog sync operations
    """
    source = models.CharField(max_length=20, choices=BlogPost.SOURCE_CHOICES)
    synced_at = models.DateTimeField(auto_now_add=True)
    posts_created = models.IntegerField(default=0)
    posts_updated = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='success')
    error_message = models.TextField(blank=True)

    class Meta:
        app_label = 'blog'
        verbose_name = "Blog Sync Log"
        verbose_name_plural = "Blog Sync Logs"
        ordering = ['-synced_at']

    def __str__(self):
        return f"{self.source} sync at {self.synced_at}"