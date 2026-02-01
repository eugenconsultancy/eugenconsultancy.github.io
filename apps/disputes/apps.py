"""
App configuration for disputes.
"""
from django.apps import AppConfig


class DisputesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.disputes'
    verbose_name = 'Dispute Resolution'
    
    def ready(self):
        """
        Import signals when app is ready. 
        Ensures the dispute handling logic is registered.
        """
        try:
            import apps.disputes.signals  # This now resolves after creating the file
        except ImportError as e:
            # Helpful for debugging why signals might fail to load (missing dependencies, etc.)
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not load signals for disputes: {e}")