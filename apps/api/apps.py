"""
App configuration for API.
"""
from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.api'
    verbose_name = 'API'
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            from . import signals  # noqa F401
        except ImportError:
            pass