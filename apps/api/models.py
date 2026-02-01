# apps/api/models.py
"""
Models for API configuration and management.
"""

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class APIToken(models.Model):
    """Custom API token model if not using Django REST Framework's default."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'api_tokens'
    
    def __str__(self):
        return f"{self.user.username}'s API Token"


class APIRequestLog(models.Model):
    """Log API requests for monitoring and analytics."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    endpoint = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    status_code = models.IntegerField()
    response_time = models.FloatField(help_text="Response time in milliseconds")
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        db_table = 'api_request_logs'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.method} {self.endpoint} - {self.status_code}"