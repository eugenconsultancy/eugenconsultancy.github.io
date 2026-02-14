from django.db import models
from media_portfolio.core.models import BaseModel


class GitHubRepo(BaseModel):
    """
    Model for GitHub repository data
    """
    name = models.CharField(max_length=200)
    full_name = models.CharField(max_length=300, unique=True)
    description = models.TextField(blank=True)
    
    # URLs
    html_url = models.URLField()
    clone_url = models.URLField()
    homepage = models.URLField(blank=True)
    
    # Stats
    stars_count = models.IntegerField(default=0)
    forks_count = models.IntegerField(default=0)
    watchers_count = models.IntegerField(default=0)
    open_issues_count = models.IntegerField(default=0)
    
    # Languages
    primary_language = models.CharField(max_length=50, blank=True)
    languages = models.JSONField(default=dict, blank=True)
    
    # Dates
    created_at_github = models.DateTimeField()
    updated_at_github = models.DateTimeField()
    pushed_at_github = models.DateTimeField()
    
    # Sync
    last_synced = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "GitHub Repository"
        verbose_name_plural = "GitHub Repositories"
        ordering = ['-stars_count']

    def __str__(self):
        return self.full_name


class GitHubSyncLog(BaseModel):
    """
    Log for GitHub sync operations
    """
    synced_at = models.DateTimeField(auto_now_add=True)
    repos_created = models.IntegerField(default=0)
    repos_updated = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='success')
    error_message = models.TextField(blank=True)

    class Meta:
        verbose_name = "GitHub Sync Log"
        verbose_name_plural = "GitHub Sync Logs"
        ordering = ['-synced_at']

    def __str__(self):
        return f"GitHub sync at {self.synced_at}"