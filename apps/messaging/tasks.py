# apps/messaging/tasks.py
import logging
from celery import shared_task
from django.utils import timezone

from apps.messaging.models import MessageAttachment
from apps.messaging.services import MessageSecurityService

logger = logging.getLogger(__name__)

@shared_task
def scan_attachment_for_viruses(attachment_id: str):
    """
    Scan a message attachment for viruses.
    """
    try:
        attachment = MessageAttachment.objects.get(id=attachment_id)
        
        # Scan file
        status, result = MessageSecurityService.scan_for_viruses(attachment.file.path)
        
        # Update attachment
        attachment.virus_scan_status = status
        attachment.virus_scan_result = result
        attachment.scanned_at = timezone.now()
        attachment.save(update_fields=[
            'virus_scan_status', 'virus_scan_result', 'scanned_at'
        ])
        
        logger.info(f"Virus scan completed for {attachment.original_filename}: {status}")
        
        # If infected, log and take action
        if status == 'infected':
            logger.warning(f"Virus detected in {attachment.original_filename}: {result}")
            
    except MessageAttachment.DoesNotExist:
        logger.error(f"Attachment {attachment_id} not found")
    except Exception as e:
        logger.error(f"Error scanning attachment {attachment_id}: {e}")


@shared_task
def cleanup_old_attachments(days=90):
    """
    Clean up old message attachments to save storage.
    """
    from django.db.models import Q
    cutoff_date = timezone.now() - timezone.timedelta(days=days)
    
    try:
        # Find old attachments from completed orders
        from apps.orders.models import Order
        
        # FIXED: Changed 'status__in' to 'state__in' to match your Order model
        completed_orders = Order.objects.filter(
            state__in=['completed', 'cancelled', 'refunded'],
            updated_at__lt=cutoff_date
        )
        
        attachments_to_delete = MessageAttachment.objects.filter(
            message__conversation__order__in=completed_orders
        )
        
        count = attachments_to_delete.count()
        
        # Delete files and database records
        for attachment in attachments_to_delete:
            try:
                # Delete the actual file from storage
                if attachment.file:
                    attachment.file.delete(save=False)
            except Exception as e:
                logger.error(f"Error deleting file {attachment.id}: {e}")
            
            # Delete the database record
            attachment.delete()
        
        logger.info(f"Cleaned up {count} old message attachments")
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_attachments: {e}")