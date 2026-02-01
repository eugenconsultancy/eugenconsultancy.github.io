from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
import logging

from .models.kpi import KPI
from .services.report_generator import AnalyticsService
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.reviews.models import Review
from apps.accounts.models import WriterProfile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def update_order_kpis(sender, instance, created, **kwargs):
    """Update KPIs when order is created or updated"""
    if instance.status == 'completed' or created:
        try:
            # Update daily KPIs
            period_end = timezone.now()
            period_start = period_end - timedelta(days=1)
            
            # Calculate relevant KPIs
            AnalyticsService.calculate_kpi('total_orders', period_start, period_end)
            AnalyticsService.calculate_kpi('order_completion_rate', period_start, period_end)
            
            if instance.status == 'completed':
                AnalyticsService.calculate_kpi('average_completion_time', period_start, period_end)
                AnalyticsService.calculate_kpi('total_revenue', period_start, period_end)
                AnalyticsService.calculate_kpi('average_order_value', period_start, period_end)
                
        except Exception as e:
            logger.error(f"Failed to update order KPIs: {str(e)}")


@receiver(post_save, sender=Payment)
def update_payment_kpis(sender, instance, created, **kwargs):
    """Update KPIs when payment is released"""
    if instance.status == 'released_to_wallet':
        try:
            period_end = timezone.now()
            period_start = period_end - timedelta(days=1)
            
            AnalyticsService.calculate_kpi('total_revenue', period_start, period_end)
            AnalyticsService.calculate_kpi('platform_revenue', period_start, period_end)
            
        except Exception as e:
            logger.error(f"Failed to update payment KPIs: {str(e)}")


@receiver(post_save, sender=Review)
def update_quality_kpis(sender, instance, created, **kwargs):
    """Update quality KPIs when review is created"""
    if created and instance.is_approved:
        try:
            period_end = timezone.now()
            period_start = period_end - timedelta(days=1)
            
            AnalyticsService.calculate_kpi('average_rating', period_start, period_end)
            AnalyticsService.calculate_kpi('customer_satisfaction', period_start, period_end)
            
        except Exception as e:
            logger.error(f"Failed to update quality KPIs: {str(e)}")


@receiver(post_save, sender=WriterProfile)
def update_writer_kpis(sender, instance, created, **kwargs):
    """Update writer KPIs when profile is updated"""
    if instance.verification_status == 'approved':
        try:
            period_end = timezone.now()
            period_start = period_end - timedelta(days=1)
            
            AnalyticsService.calculate_kpi('active_writers', period_start, period_end)
            AnalyticsService.calculate_kpi('writer_approval_rate', period_start, period_end)
            
        except Exception as e:
            logger.error(f"Failed to update writer KPIs: {str(e)}")


@receiver(post_save, sender=KPI)
def schedule_kpi_calculation(sender, instance, created, **kwargs):
    """Schedule KPI calculation when created or activated"""
    if created or (instance.is_active and instance.is_auto_calculated):
        try:
            from .tasks import calculate_kpi_task
            
            # Schedule based on calculation period
            if instance.calculation_period == 'daily':
                # Schedule for midnight
                calculate_kpi_task.apply_async(
                    args=[instance.slug],
                    countdown=10  # Run after 10 seconds for initial calculation
                )
                
            logger.info(f"Scheduled KPI calculation for {instance.slug}")
            
        except Exception as e:
            logger.error(f"Failed to schedule KPI calculation: {str(e)}")