from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserAILimits, AIToolConfiguration

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_ai_limits(sender, instance, created, **kwargs):
    """Create AI limits for new users"""
    if created:
        UserAILimits.objects.create(user=instance)


@receiver(post_save, sender=AIToolConfiguration)
def clear_tool_config_cache(sender, instance, **kwargs):
    """Clear cache when tool configuration changes"""
    from django.core.cache import cache
    cache_key = f"citation_style_{instance.tool_type}"
    cache.delete(cache_key)