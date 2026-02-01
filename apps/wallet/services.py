from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db import models
from django.db.models import Sum, F
from django.core.exceptions import ValidationError, PermissionDenied
from django.conf import settings
from apps.orders.models import Order
from apps.payments.models import Payment
import logging
import uuid

logger = logging.getLogger(__name__)


class WalletService:
    """Service for managing wallet operations"""
    
    @staticmethod
    def get_or_create_wallet(user):
        """Get or create wallet for user"""
        from .models import Wallet
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            defaults={
                'minimum_payout_threshold': Decimal('50.00')
            }
        )
        return wallet
    
    @staticmethod
    def calculate_commission(order_amount, writer_level):
        """Calculate commission based on writer level"""
        from .models import CommissionRate
        
        try:
            rate = CommissionRate.objects.get(
                writer_level=writer_level,
                is_active=True,
                effective_from__lte=timezone.now(),
                effective_until__gte=timezone.now() | models.Q(effective_until__isnull=True)
            )
            commission = (order_amount * rate.commission_percentage) / Decimal('100.00')
            return commission.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except CommissionRate.DoesNotExist:
            # Default commission
            default_rate = Decimal('20.00')  # 20%
            return (order_amount * default_rate) / Decimal('100.00')
    
    @staticmethod
    @db_transaction.atomic
    def credit_order_payment(order_id, writer_id):
        """Credit writer wallet for completed order"""
        from .models import Wallet, Transaction
        from apps.accounts.models import User
        
        try:
            order = Order.objects.select_for_update().get(id=order_id)
            writer = User.objects.get(id=writer_id)
            
            if order.status != 'completed':
                raise ValidationError("Order must be completed to release payment")
            
            if order.writer_id != writer.id:
                raise PermissionDenied("Writer does not own this order")
            
            # Get or create wallet
            wallet = WalletService.get_or_create_wallet(writer)
            
            # Calculate writer earnings (after commission)
            order_total = order.total_price
            commission = WalletService.calculate_commission(
                order_total,
                writer.writer_profile.level if hasattr(writer, 'writer_profile') else 'new'
            )
            writer_earnings = order_total - commission
            
            # Create transaction record
            transaction = Transaction.objects.create(
                wallet=wallet,
                transaction_type='credit',
                amount=writer_earnings,
                status='pending',
                reference_type='order',
                reference_id=order_id,
                description=f"Payment for Order #{order.order_number}",
                metadata={
                    'order_number': order.order_number,
                    'order_total': str(order_total),
                    'commission': str(commission),
                    'commission_rate': '20%',  # Would be dynamic
                },
                balance_before=wallet.balance,
                balance_after=wallet.balance + writer_earnings,
                initiated_by=writer
            )
            
            # Update wallet balances
            wallet.balance = F('balance') + writer_earnings
            wallet.total_earned = F('total_earned') + writer_earnings
            wallet.pending_balance = F('pending_balance') - writer_earnings
            wallet.save(update_fields=['balance', 'total_earned', 'pending_balance'])
            
            # Refresh from DB
            wallet.refresh_from_db()
            
            # Mark transaction as completed
            transaction.mark_completed()
            transaction.save()
            
            # Update order payment status
            payment = Payment.objects.filter(order=order).first()
            if payment:
                payment.release_to_writer()
                payment.save()
            
            logger.info(f"Credited ${writer_earnings} to wallet {wallet.id} for order {order_id}")
            return transaction
            
        except Exception as e:
            logger.error(f"Failed to credit order payment: {str(e)}")
            raise
    
    @staticmethod
    @db_transaction.atomic
    def request_payout(wallet_id, amount, payout_method, payout_details):
        """Request payout from wallet"""
        from .models import Wallet, PayoutRequest, Transaction
        
        try:
            wallet = Wallet.objects.select_for_update().get(id=wallet_id)
            
            # Validate amount
            amount = Decimal(str(amount))
            if amount <= Decimal('0'):
                raise ValidationError("Payout amount must be positive")
            
            if wallet.balance < amount:
                raise ValidationError("Insufficient balance")
            
            if amount < wallet.minimum_payout_threshold:
                raise ValidationError(
                    f"Amount below minimum payout threshold of ${wallet.minimum_payout_threshold}"
                )
            
            # Create payout request
            payout_request = PayoutRequest.objects.create(
                wallet=wallet,
                amount=amount,
                payout_method=payout_method,
                payout_details=payout_details,
                status='pending'
            )
            
            # Create pending transaction
            transaction = Transaction.objects.create(
                wallet=wallet,
                transaction_type='debit',
                amount=amount,
                status='pending',
                reference_type='payout',
                reference_id=payout_request.id,
                description=f"Payout request via {payout_method}",
                metadata={
                    'payout_method': payout_method,
                    'payout_details': payout_details,
                },
                balance_before=wallet.balance,
                balance_after=wallet.balance - amount,
                initiated_by=wallet.user
            )
            
            # Hold funds
            wallet.balance = F('balance') - amount
            wallet.save(update_fields=['balance'])
            wallet.refresh_from_db()
            
            logger.info(f"Created payout request {payout_request.id} for ${amount}")
            return payout_request
            
        except Exception as e:
            logger.error(f"Failed to create payout request: {str(e)}")
            raise
    
    @staticmethod
    @db_transaction.atomic
    def process_payout(payout_request_id, admin_user, reference=None):
        """Process and complete payout"""
        from .models import PayoutRequest, Transaction, Wallet
        
        try:
            payout = PayoutRequest.objects.select_for_update().get(id=payout_request_id)
            wallet = payout.wallet
            
            if payout.status != 'approved':
                raise ValidationError("Payout must be approved before processing")
            
            # Find associated transaction
            transaction = Transaction.objects.filter(
                reference_type='payout',
                reference_id=payout.id,
                status='pending'
            ).first()
            
            if not transaction:
                raise ValidationError("No pending transaction found for payout")
            
            # Update payout status
            payout.start_processing()
            payout.save()
            
            # Simulate processing (integrate with payment gateway here)
            # In production, this would call PayPal/Stripe/etc API
            
            # Complete payout
            payout.complete(reference or f"PYT-{payout.id.hex[:8].upper()}")
            payout.processed_by = admin_user
            payout.save()
            
            # Complete transaction
            transaction.mark_completed()
            transaction.save()
            
            # Update wallet
            wallet.total_paid_out = F('total_paid_out') + payout.amount
            wallet.save(update_fields=['total_paid_out'])
            wallet.refresh_from_db()
            
            logger.info(f"Processed payout {payout.id} for ${payout.amount}")
            return payout
            
        except Exception as e:
            logger.error(f"Failed to process payout: {str(e)}")
            raise
    
    @staticmethod
    def get_wallet_summary(wallet_id):
        """Get comprehensive wallet summary"""
        from .models import Wallet, Transaction, PayoutRequest
        
        wallet = Wallet.objects.get(id=wallet_id)
        
        # Calculate statistics
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        
        recent_credits = Transaction.objects.filter(
            wallet=wallet,
            transaction_type='credit',
            status='completed',
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        pending_payouts = PayoutRequest.objects.filter(
            wallet=wallet,
            status__in=['pending', 'approved', 'processing']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'wallet': wallet,
            'available_balance': wallet.balance,
            'pending_balance': wallet.pending_balance,
            'total_earned': wallet.total_earned,
            'total_paid_out': wallet.total_paid_out,
            'recent_earnings_30d': recent_credits,
            'pending_payouts': pending_payouts,
            'minimum_threshold': wallet.minimum_payout_threshold,
            'eligible_for_payout': wallet.available_for_payout,
        }
    
    @staticmethod
    def calculate_writer_level(writer):
        """Calculate writer level based on performance"""
        from apps.orders.models import Order
        from apps.reviews.models import Review
        
        if not hasattr(writer, 'writer_profile'):
            return 'new'
        
        completed_orders = Order.objects.filter(
            writer=writer,
            status='completed'
        ).count()
        
        avg_rating = Review.objects.filter(
            order__writer=writer,
            is_active=True
        ).aggregate(avg=models.Avg('rating'))['avg'] or 0
        
        if completed_orders >= 100 and avg_rating >= 4.8:
            return 'elite'
        elif completed_orders >= 50:
            return 'expert'
        elif completed_orders >= 20:
            return 'experienced'
        elif completed_orders >= 5:
            return 'regular'
        else:
            return 'new'


class EscrowToWalletService:
    """Service for handling escrow to wallet transitions"""
    
    @staticmethod
    @db_transaction.atomic
    def move_to_pending_wallet(payment_id):
        """Move funds from escrow to pending wallet when order is assigned"""
        from .models import Wallet, Transaction
        from apps.payments.models import Payment
        
        try:
            payment = Payment.objects.select_for_update().get(id=payment_id)
            
            if payment.status != 'held_in_escrow':
                raise ValidationError("Payment must be in escrow")
            
            # Get writer wallet
            writer = payment.order.writer
            if not writer:
                raise ValidationError("Order not assigned to writer")
            
            wallet = WalletService.get_or_create_wallet(writer)
            
            # Calculate writer earnings
            order_total = payment.order.total_price
            writer_earnings = order_total  # Full amount goes to pending
            
            # Create pending transaction
            transaction = Transaction.objects.create(
                wallet=wallet,
                transaction_type='credit',
                amount=writer_earnings,
                status='pending',
                reference_type='order',
                reference_id=payment.order.id,
                description=f"Pending payment for Order #{payment.order.order_number}",
                metadata={
                    'order_number': payment.order.order_number,
                    'is_pending': True,
                },
                balance_before=wallet.pending_balance,
                balance_after=wallet.pending_balance + writer_earnings,
                initiated_by=writer
            )
            
            # Update pending balance
            wallet.pending_balance = F('pending_balance') + writer_earnings
            wallet.save(update_fields=['pending_balance'])
            
            logger.info(f"Moved ${writer_earnings} to pending wallet for payment {payment_id}")
            return transaction
            
        except Exception as e:
            logger.error(f"Failed to move to pending wallet: {str(e)}")
            raise