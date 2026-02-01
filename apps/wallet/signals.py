from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.conf import settings
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.accounts.models import User
from .models import Wallet
from .services import WalletService, EscrowToWalletService
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    """Create wallet for new writer users"""
    if created and instance.role == 'writer':
        WalletService.get_or_create_wallet(instance)
        logger.info(f"Created wallet for new writer: {instance.email}")


@receiver(post_save, sender=Order)
def handle_order_status_change(sender, instance, created, **kwargs):
    """Handle wallet updates based on order status changes"""
    if created:
        return
    
    # Check if status changed
    if instance.tracker.has_changed('status'):
        try:
            with transaction.atomic():
                if instance.status == 'assigned' and instance.writer:
                    # Move funds from escrow to pending wallet
                    payment = Payment.objects.filter(order=instance).first()
                    if payment and payment.status == 'held_in_escrow':
                        EscrowToWalletService.move_to_pending_wallet(payment.id)
                        
                elif instance.status == 'completed' and instance.writer:
                    # Release pending funds to available balance
                    WalletService.credit_order_payment(instance.id, instance.writer.id)
                    
                elif instance.status in ['cancelled', 'refunded']:
                    # Handle refunds/cancellations
                    from .services import WalletService
                    # This would trigger refund logic
                    logger.info(f"Order {instance.id} cancelled/refunded, wallet adjustments needed")
                    
        except Exception as e:
            logger.error(f"Failed to handle order status change for wallet: {str(e)}")
            # Don't raise to prevent blocking order save


@receiver(pre_save, sender=Wallet)
def validate_wallet_balance(sender, instance, **kwargs):
    """Validate wallet balance doesn't go negative"""
    if instance.balance < 0:
        raise ValueError("Wallet balance cannot be negative")
    
    if instance.pending_balance < 0:
        raise ValueError("Pending balance cannot be negative")