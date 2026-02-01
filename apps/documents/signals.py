# apps/documents/signals.py
import logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from apps.orders.models import Order
from apps.documents.models import GeneratedDocument
from apps.documents.services.pdf_generator import PDFGenerationService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def generate_order_documents(sender, instance, created, **kwargs):
    """
    Generate documents when order reaches certain statuses.
    """
    if created:
        return  # Skip new orders
    
    # Get the old status from the database
    try:
        old_order = Order.objects.get(id=instance.id)
        old_status = old_order.status
    except Order.DoesNotExist:
        old_status = None
    
    # Check if status changed
    if old_status != instance.status:
        if instance.status == 'paid':
            # Generate invoice when order is paid
            PDFGenerationService.generate_invoice(instance)
            logger.info(f"Invoice generation triggered for order {instance.order_id}")
        
        elif instance.status == 'delivered':
            # Generate delivery cover when order is delivered
            PDFGenerationService.generate_delivery_cover(instance)
            logger.info(f"Delivery cover generation triggered for order {instance.order_id}")
        
        elif instance.status == 'completed':
            # Generate completion certificate when order is completed
            PDFGenerationService.generate_completion_certificate(instance)
            logger.info(f"Completion certificate generation triggered for order {instance.order_id}")


@receiver(pre_delete, sender=GeneratedDocument)
def delete_document_file(sender, instance, **kwargs):
    """
    Delete document file when GeneratedDocument is deleted.
    """
    try:
        if instance.file:
            instance.file.delete(save=False)
            logger.info(f"Deleted document file: {instance.file.name}")
    except Exception as e:
        logger.error(f"Error deleting document file {instance.file.name}: {e}")