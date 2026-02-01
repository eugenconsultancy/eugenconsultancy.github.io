from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from django_fsm import FSMField, transition
from decimal import Decimal
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator


class Wallet(models.Model):
    """Writer wallet for managing earnings and payouts"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet'
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    pending_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_earned = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_paid_out = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    is_active = models.BooleanField(default=True)
    minimum_payout_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('50.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    default_payment_method = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('paypal', 'PayPal'),
            ('bank_transfer', 'Bank Transfer'),
            ('skrill', 'Skrill'),
            ('payoneer', 'Payoneer'),
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'
    
    def __str__(self):
        return f"Wallet: {self.user.email} - ${self.balance}"
    
    @property
    def available_for_payout(self):
        return self.balance >= self.minimum_payout_threshold
    
    @property
    def pending_release(self):
        return self.pending_balance




class WalletTransaction(models.Model):  # ← ADD THIS MODEL
    TRANSACTION_TYPES = (
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('transfer', 'Transfer'),
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('commission', 'Commission'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    
    # FIXED: Changed related_name to avoid conflict
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='wallet_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type}: {self.amount} {self.currency} ({self.status})"
    

    
class Transaction(models.Model):
    """Wallet transaction record"""
    TRANSACTION_TYPES = [
        ('credit', 'Credit - Order Payment'),
        ('debit', 'Debit - Payout'),
        ('refund', 'Refund - Order Cancelled'),
        ('adjustment', 'Manual Adjustment'),
        ('commission', 'Platform Commission'),
        ('bonus', 'Performance Bonus'),
        ('penalty', 'Quality Penalty'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('reversed', 'Reversed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # FIXED: Changed related_name to avoid conflict
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='main_transactions'  # Changed from 'transactions'
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    status = FSMField(
        default='pending',
        choices=STATUS_CHOICES,
        protected=True
    )
    reference_type = models.CharField(
        max_length=50,
        choices=[
            ('order', 'Order'),
            ('payout', 'Payout'),
            ('refund', 'Refund'),
            ('adjustment', 'Adjustment'),
            ('other', 'Other'),
        ]
    )
    reference_id = models.UUIDField(null=True, blank=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    balance_before = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_transactions'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reference_type', 'reference_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['wallet', 'created_at']),
        ]
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
    
    def __str__(self):
        return f"{self.get_transaction_type_display()}: ${self.amount}"
    
    @transition(field=status, source='pending', target='completed')
    def mark_completed(self):
        """Mark transaction as completed"""
        self.completed_at = timezone.now()
    
    @transition(field=status, source='pending', target='failed')
    def mark_failed(self):
        """Mark transaction as failed"""
        pass
    
    @transition(field=status, source=['pending', 'completed'], target='cancelled')
    def mark_cancelled(self):
        """Mark transaction as cancelled"""
        pass


class PayoutRequest(models.Model):
    """Writer payout requests"""
    PAYOUT_METHODS = [
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer'),
        ('skrill', 'Skrill'),
        ('payoneer', 'Payoneer'),
    ]
    
    PAYOUT_STATUS = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved for Processing'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='payout_requests'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payout_method = models.CharField(max_length=20, choices=PAYOUT_METHODS)
    payout_details = models.JSONField(default=dict)
    status = FSMField(
        default='pending',
        choices=PAYOUT_STATUS,
        protected=True
    )
    admin_notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_payouts'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    transaction_reference = models.CharField(max_length=255, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payout Request'
        verbose_name_plural = 'Payout Requests'
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gte=Decimal('0.01')),
                name='payout_amount_positive'
            ),
        ]
    
    def __str__(self):
        return f"Payout: {self.wallet.user.email} - ${self.amount}"
    
    @property
    def is_eligible(self):
        return (
            self.wallet.balance >= self.amount >= self.wallet.minimum_payout_threshold
        )
    
    @transition(field=status, source='pending', target='approved')
    def approve(self, admin_user):
        """Approve payout request"""
        self.processed_by = admin_user
        self.processed_at = timezone.now()
    
    @transition(field=status, source='pending', target='rejected')
    def reject(self, reason):
        """Reject payout request"""
        self.rejection_reason = reason
    
    @transition(field=status, source='approved', target='processing')
    def start_processing(self):
        """Start processing payout"""
        pass
    
    @transition(field=status, source='processing', target='completed')
    def complete(self, reference):
        """Complete payout"""
        self.transaction_reference = reference
        self.processed_at = timezone.now()
    
    @transition(field=status, source=['pending', 'approved'], target='cancelled')
    def cancel(self):
        """Cancel payout request"""
        pass


class CommissionRate(models.Model):
    """Platform commission rates"""
    WRITER_LEVELS = [
        ('new', 'New Writer (0-5 orders)'),
        ('regular', 'Regular Writer (6-20 orders)'),
        ('experienced', 'Experienced Writer (21-50 orders)'),
        ('expert', 'Expert Writer (51+ orders)'),
        ('elite', 'Elite Writer (100+ orders, 4.8+ rating)'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    writer_level = models.CharField(
        max_length=20,
        choices=WRITER_LEVELS,
        unique=True
    )
    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    minimum_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('5.00'))]
    )
    minimum_completed_orders = models.PositiveIntegerField(default=0)
    bonus_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(default=timezone.now)
    effective_until = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['commission_percentage']
        verbose_name = 'Commission Rate'
        verbose_name_plural = 'Commission Rates'
    
    def __str__(self):
        return f"{self.get_writer_level_display()}: {self.commission_percentage}%"
    
    @property
    def is_currently_effective(self):
        now = timezone.now()
        if self.effective_until and now > self.effective_until:
            return False
        return now >= self.effective_from


class WriterBonus(models.Model):
    """Performance bonuses for writers"""
    BONUS_TYPES = [
        ('performance', 'Performance Bonus'),
        ('retention', 'Retention Bonus'),
        ('quality', 'Quality Bonus'),
        ('referral', 'Referral Bonus'),
        ('holiday', 'Holiday Bonus'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='bonuses'
    )
    bonus_type = models.CharField(max_length=20, choices=BONUS_TYPES)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    reason = models.TextField()
    calculation_period_start = models.DateField()
    calculation_period_end = models.DateField()
    metrics = models.JSONField(default=dict)
    awarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Writer Bonus'
        verbose_name_plural = 'Writer Bonuses'
    
    def __str__(self):
        return f"{self.get_bonus_type_display()}: ${self.amount}"