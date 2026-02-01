from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from .models import Review, WriterRatingSummary
from .moderation import ReviewModerationService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Review)
def handle_review_creation(sender, instance, created, **kwargs):
    """Handle review creation and updates"""
    if created:
        # Auto-moderate new reviews
        result = ReviewModerationService.auto_moderate_review(instance)
        logger.info(f"Auto-moderated review {instance.id}: {result}")
        
        # Notify writer about new review
        if instance.is_approved:
            from ..notifications.services import NotificationService
            NotificationService.notify_user(
                user=instance.writer,
                subject="New Review Received",
                message=f"You received a {instance.rating}-star review for Order #{instance.order.order_number}",
                notification_type='new_review'
            )
    
    # Update writer rating summary
    try:
        with transaction.atomic():
            ReviewModerationService.update_writer_ratings(instance.writer)
    except Exception as e:
        logger.error(f"Failed to update writer ratings: {str(e)}")


@receiver(pre_save, sender=Review)
def validate_review(sender, instance, **kwargs):
    """Validate review before saving"""
    
    # Ensure customer is the order customer
    if instance.customer != instance.order.customer:
        raise ValueError("Review customer must match order customer")
    
    # Ensure writer is the order writer
    if instance.writer != instance.order.writer:
        raise ValueError("Review writer must match order writer")
    
    # Ensure order is completed
    if instance.order.status != 'completed':
        raise ValueError("Can only review completed orders")


@receiver(post_save, sender=WriterRatingSummary)
def handle_rating_summary_update(sender, instance, created, **kwargs):
    """Handle rating summary updates"""
    if not created and instance.average_rating < 2.5 and instance.total_reviews >= 10:
        # Trigger critical alert for very low ratings
        from ..notifications.services import NotificationService
        NotificationService.notify_admins(
            subject=f"Critical: Writer {instance.writer.email} Has Very Low Ratings",
            message=f"Writer {instance.writer.email} has average rating of {instance.average_rating}",
            notification_type='critical_rating_alert'
        )


@receiver(post_delete, sender=Review)
def handle_review_deletion(sender, instance, **kwargs):
    """Handle review deletion"""
    # Update writer rating summary
    try:
        ReviewModerationService.update_writer_ratings(instance.writer)
    except Exception as e:
        logger.error(f"Failed to update writer ratings after deletion: {str(e)}")