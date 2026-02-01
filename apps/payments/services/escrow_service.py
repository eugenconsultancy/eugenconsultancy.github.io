from typing import Dict, Optional
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings

from apps.payments.models import Payment
from apps.orders.models import Order
from apps.wallet.models import WalletTransaction


class EscrowService:
    """Service for managing escrow payments and releases."""
    
    @classmethod
    @transaction.atomic
    def create_escrow_payment(cls, order_id: int, user_id: int, amount: Decimal, **kwargs) -> Payment:
        """
        Create a new payment and hold it in escrow.
        
        Args:
            order_id: ID of the order being paid for
            user_id: ID of the user making payment
            amount: Payment amount
            **kwargs: Additional payment parameters
            
        Returns:
            Created Payment object
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            order = Order.objects.get(id=order_id)
            user = User.objects.get(id=user_id)
        except (Order.DoesNotExist, User.DoesNotExist) as e:
            raise ValidationError(f"Invalid order or user: {str(e)}")
        
        # Validate payment amount matches order price
        if amount != order.price:
            raise ValidationError(
                f"Payment amount ({amount}) does not match order price ({order.price})"
            )
        
        # Perform fraud check
        fraud_check_result = cls._perform_fraud_check(user, amount, **kwargs)
        
        # Create payment
        payment = Payment.objects.create(
            order=order,
            user=user,
            amount=amount,
            fraud_check_passed=fraud_check_result['passed'],
            fraud_check_details=fraud_check_result['details'],
            ip_address=kwargs.get('ip_address'),
            user_agent=kwargs.get('user_agent'),
            gateway_response=kwargs.get('gateway_response', {}),
            gateway_transaction_id=kwargs.get('gateway_transaction_id', ''),
        )
        
        # Start processing
        payment.start_processing()
        payment.save()
        
        # If fraud check passed, hold in escrow
        if fraud_check_result['passed']:
            payment.hold_in_escrow()
            payment.save()
            
            # Update order state to paid
            order.mark_as_paid(payment)
            order.save()
        
        return payment
    
    @classmethod
    @transaction.atomic
    def release_escrow_funds(cls, payment_id: int, admin_user=None) -> Payment:
        """
        Release funds from escrow to writer's wallet.
        
        Args:
            payment_id: ID of the payment to release
            admin_user: Admin user performing release (optional for auto-release)
            
        Returns:
            Updated Payment object
        """
        payment = Payment.objects.select_related('order', 'order__writer').get(id=payment_id)
        
        # Validate payment can be released
        if not payment.can_be_released:
            raise ValidationError(
                f"Cannot release payment in state: {payment.state}"
            )
        
        # Check if manual admin release is required
        if admin_user and not admin_user.is_staff:
            raise PermissionError("Only staff can manually release escrow funds")
        
        # Check if automatic release conditions are met
        if not admin_user:
            if not payment.escrow_held_until or payment.escrow_held_until > timezone.now():
                raise ValidationError("Escrow period has not ended yet")
            
            if payment.order and payment.order.state != 'completed':
                raise ValidationError("Order is not completed")
        
        # Release funds
        payment.release_to_wallet()
        payment.save()
        
        # Update writer's wallet
        cls._update_writer_wallet(payment)
        
        return payment
    
    @classmethod
    @transaction.atomic
    def refund_order(cls, order_id: int, amount: Optional[Decimal] = None) -> Payment:
        """
        Refund payment for an order.
        
        Args:
            order_id: ID of the order to refund
            amount: Refund amount (None for full refund)
            
        Returns:
            Updated Payment object
        """
        try:
            order = Order.objects.get(id=order_id)
            payment = order.payment
        except (Order.DoesNotExist, AttributeError) as e:
            raise ValidationError(f"Order or payment not found: {str(e)}")
        
        # Validate payment can be refunded
        valid_states = ['held_in_escrow', 'processing']
        if payment.state not in valid_states:
            raise ValidationError(
                f"Cannot refund payment in state: {payment.state}"
            )
        
        # Determine refund amount
        refund_amount = amount or payment.amount
        
        if refund_amount > payment.amount:
            raise ValidationError(
                f"Refund amount ({refund_amount}) exceeds payment amount ({payment.amount})"
            )
        
        # Process refund
        payment.refund(refund_amount)
        payment.save()
        
        # Create refund record
        from apps.payments.models import Refund
        
        Refund.objects.create(
            payment=payment,
            order=order,
            requested_by=order.client,
            amount=refund_amount,
            original_amount=payment.amount,
            currency=payment.currency,
            refund_type='full' if refund_amount == payment.amount else 'partial',
            refund_reason='order_cancellation',
            custom_reason=f'Refund for order #{order.order_number}',
        )
        
        return payment
    
    @classmethod
    def get_escrow_balance(cls) -> Dict:
        """
        Get total escrow balance and breakdown.
        
        Returns:
            Dictionary with escrow balance information
        """
        from django.db.models import Sum
        
        # Payments held in escrow
        escrow_payments = Payment.objects.filter(state='held_in_escrow')
        
        total_balance = escrow_payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        platform_fee_total = escrow_payments.aggregate(
            total=Sum('platform_fee')
        )['total'] or Decimal('0.00')
        
        writer_amount_total = escrow_payments.aggregate(
            total=Sum('writer_amount')
        )['total'] or Decimal('0.00')
        
        # Breakdown by time in escrow
        now = timezone.now()
        breakdown = {
            'less_than_24h': Decimal('0.00'),
            '1_to_3_days': Decimal('0.00'),
            '3_to_7_days': Decimal('0.00'),
            'more_than_7_days': Decimal('0.00'),
        }
        
        for payment in escrow_payments:
            if payment.held_in_escrow_at:
                time_in_escrow = now - payment.held_in_escrow_at
                
                if time_in_escrow.days < 1:
                    breakdown['less_than_24h'] += payment.amount
                elif time_in_escrow.days < 3:
                    breakdown['1_to_3_days'] += payment.amount
                elif time_in_escrow.days < 7:
                    breakdown['3_to_7_days'] += payment.amount
                else:
                    breakdown['more_than_7_days'] += payment.amount
        
        return {
            'total_balance': total_balance,
            'platform_fee_total': platform_fee_total,
            'writer_amount_total': writer_amount_total,
            'payment_count': escrow_payments.count(),
            'breakdown_by_time': breakdown,
            'pending_releases': cls._get_pending_releases_count(),
        }
    
    @classmethod
    def _perform_fraud_check(cls, user, amount: Decimal, **kwargs) -> Dict:
        """
        Perform fraud check on payment.
        
        Args:
            user: User making payment
            amount: Payment amount
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with fraud check results
        """
        # In production, integrate with fraud detection service
        # For now, implement basic checks
        
        checks = {
            'high_amount_check': amount <= Decimal('5000.00'),  # Max $5000
            'user_history_check': cls._check_user_history(user),
            'velocity_check': cls._check_payment_velocity(user),
            'ip_check': cls._check_ip_address(kwargs.get('ip_address')),
        }
        
        passed = all(checks.values())
        
        return {
            'passed': passed,
            'details': {
                'checks_performed': checks,
                'risk_score': cls._calculate_risk_score(checks),
                'timestamp': timezone.now().isoformat(),
            }
        }
    
    @classmethod
    def _check_user_history(cls, user) -> bool:
        """Check user's payment history for fraud patterns."""
        # Check for failed payments
        failed_payments = Payment.objects.filter(
            user=user,
            state='failed'
        ).count()
        
        # Check for recent refunds
        recent_refunds = Payment.objects.filter(
            user=user,
            state='refunded',
            refunded_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).count()
        
        return failed_payments < 3 and recent_refunds < 2
    
    @classmethod
    def _check_payment_velocity(cls, user) -> bool:
        """Check payment velocity (multiple payments in short time)."""
        one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
        
        recent_payments = Payment.objects.filter(
            user=user,
            created_at__gte=one_hour_ago
        ).count()
        
        return recent_payments < 3
    
    @classmethod
    def _check_ip_address(cls, ip_address: Optional[str]) -> bool:
        """Check IP address for known fraud patterns."""
        if not ip_address:
            return True
        
        # Check for VPN/proxy (simplified - in production use service like MaxMind)
        # For now, just check if IP is in suspicious ranges
        suspicious_prefixes = ['192.168.', '10.', '172.16.']
        
        if any(ip_address.startswith(prefix) for prefix in suspicious_prefixes):
            return False
        
        return True
    
    @classmethod
    def _calculate_risk_score(cls, checks: Dict) -> int:
        """Calculate risk score based on fraud checks."""
        score = 0
        
        if not checks.get('high_amount_check', True):
            score += 30
        
        if not checks.get('user_history_check', True):
            score += 25
        
        if not checks.get('velocity_check', True):
            score += 20
        
        if not checks.get('ip_check', True):
            score += 25
        
        return min(score, 100)
    
    @classmethod
    def _update_writer_wallet(cls, payment):
        """Update writer's wallet with released funds."""
        if payment.order and payment.order.writer:
            WalletTransaction.objects.create(
                user=payment.order.writer,
                amount=payment.writer_amount,
                transaction_type='order_payment',
                payment=payment,
                order=payment.order,
                status='completed',
                completed_at=timezone.now(),
            )
    
    @classmethod
    def _get_pending_releases_count(cls) -> int:
        """Get count of payments ready for release."""
        now = timezone.now()
        
        return Payment.objects.filter(
            state='held_in_escrow',
            escrow_held_until__lte=now,
            order__state='completed'
        ).count()
    
    @classmethod
    def auto_release_eligible_funds(cls) -> int:
        """
        Automatically release funds that are eligible.
        
        Returns:
            Number of payments released
        """
        released_count = 0
        now = timezone.now()
        
        eligible_payments = Payment.objects.filter(
            state='held_in_escrow',
            escrow_held_until__lte=now,
            order__state='completed'
        )
        
        for payment in eligible_payments:
            try:
                cls.release_escrow_funds(payment.id)
                released_count += 1
            except (ValidationError, PermissionError) as e:
                # Log error but continue with other payments
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to auto-release payment {payment.id}: {str(e)}")
        
        return released_count