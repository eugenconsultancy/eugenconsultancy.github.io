"""
App configuration for revisions.
"""
from django.apps import AppConfig


class RevisionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.revisions'
    verbose_name = 'Revision Management'
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.revisions.signals  # noqa F401
        except ImportError:
            pass