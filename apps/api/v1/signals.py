"""
Signals for API v1.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def create_api_user_profile(sender, instance, created, **kwargs):
    """
    Create API-related profile when a user is created.
    """
    if created:
        # Initialize API-related data for new users
        # Example: create API token, default permissions, etc.
        pass


@receiver(post_delete, sender=User)
def cleanup_api_data(sender, instance, **kwargs):
    """
    Clean up API-related data when user is deleted.
    """
    # Clean up API tokens, logs, etc.
    pass


# Add more API-specific signal handlers as needed