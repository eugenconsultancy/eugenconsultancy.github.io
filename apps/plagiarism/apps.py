"""
App configuration for plagiarism detection.
"""
from django.apps import AppConfig


class PlagiarismConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.plagiarism'
    verbose_name = 'Plagiarism Detection'

    def ready(self):
        """Import signals to connect plagiarism scans to model events."""
        try:
            import apps.plagiarism.signals  # This will now resolve
        except ImportError:
            pass