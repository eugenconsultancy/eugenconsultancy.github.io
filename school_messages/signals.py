from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Message, HolidayNotice

@receiver(post_save, sender=Message)
def handle_message_post_save(sender, instance, created, **kwargs):
    """Handle actions after a message is saved"""
    if created and instance.is_published:
        # If message is published immediately, set published_at
        instance.published_at = timezone.now()
        instance.save(update_fields=['published_at'])

@receiver(post_save, sender=HolidayNotice)
def handle_holiday_notice_post_save(sender, instance, created, **kwargs):
    """Handle actions after a holiday notice is saved"""
    if created and instance.is_active:
        # Check if holiday is current or upcoming
        today = timezone.now().date()
        if instance.start_date <= today <= instance.end_date:
            # Holiday is current - create urgent notifications
            from .views import create_holiday_notifications
            create_holiday_notifications(instance)