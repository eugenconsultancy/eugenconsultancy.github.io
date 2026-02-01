"""
App configuration for API v1.
"""
from django.apps import AppConfig


class ApiV1Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.api.v1'
    verbose_name = 'API v1'
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.api.v1.signals  # noqa F401
        except ImportError:
            pass