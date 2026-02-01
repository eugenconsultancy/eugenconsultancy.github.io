import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.utils import timezone
from django_fsm import FSMField, transition
from django.conf import settings


class Payment(models.Model):
    """Payment model with escrow lifecycle management."""
    
    # State choices
    STATE_CHOICES = (
        ('initiated', _('Initiated')),
        ('processing', _('Processing')),
        ('held_in_escrow', _('Held in Escrow')),
        ('released_to_wallet', _('Released to Wallet')),
        ('refunded', _('Refunded')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
    )
    
    # Payment method choices
    class PaymentMethod(models.TextChoices):
        CREDIT_CARD = 'credit_card', _('Credit Card')
        DEBIT_CARD = 'debit_card', _('Debit Card')
        BANK_TRANSFER = 'bank_transfer', _('Bank Transfer')
        PAYPAL = 'paypal', _('PayPal')
        STRIPE = 'stripe', _('Stripe')
        WALLET = 'wallet', _('Wallet Balance')
    
    # Payment identification
    payment_id = models.UUIDField(
        _('payment ID'),
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    
    reference_number = models.CharField(
        _('reference number'),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_('External payment reference/transaction ID')
    )
    
    # Relationships
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payment',
        verbose_name=_('order'),
        null=True,
        blank=True,
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name=_('user')
    )
    
    # Payment details
    amount = models.DecimalField(
        _('amount'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text=_('Payment amount in platform currency')
    )
    
    currency = models.CharField(
        _('currency'),
        max_length=3,
        default='USD',
        help_text=_('3-letter currency code (ISO 4217)')
    )
    
    payment_method = models.CharField(
        _('payment method'),
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.STRIPE,
    )
    
    # State management
    state = FSMField(
        _('payment state'),
        default='initiated',
        choices=STATE_CHOICES,
        protected=True,
    )
    
    # Escrow details
    escrow_held_until = models.DateTimeField(
        _('escrow held until'),
        null=True,
        blank=True,
        help_text=_('Date until funds are held in escrow')
    )
    
    platform_fee = models.DecimalField(
        _('platform fee'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
    )
    
    writer_amount = models.DecimalField(
        _('writer amount'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text=_('Amount reserved for writer payment')
    )
    
    # Transaction details
    gateway_response = models.JSONField(
        _('gateway response'),
        null=True,
        blank=True,
        help_text=_('Raw response from payment gateway')
    )
    
    gateway_transaction_id = models.CharField(
        _('gateway transaction ID'),
        max_length=100,
        blank=True,
    )
    
    # Security & Compliance
    ip_address = models.GenericIPAddressField(
        _('IP address'),
        null=True,
        blank=True,
    )
    
    user_agent = models.TextField(
        _('user agent'),
        blank=True,
    )
    
    fraud_check_passed = models.BooleanField(
        _('fraud check passed'),
        default=False,
    )
    
    fraud_check_details = models.JSONField(
        _('fraud check details'),
        null=True,
        blank=True,
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
    )
    
    processed_at = models.DateTimeField(
        _('processed at'),
        null=True,
        blank=True,
    )
    
    held_in_escrow_at = models.DateTimeField(
        _('held in escrow at'),
        null=True,
        blank=True,
    )
    
    released_at = models.DateTimeField(
        _('released at'),
        null=True,
        blank=True,
    )
    
    refunded_at = models.DateTimeField(
        _('refunded at'),
        null=True,
        blank=True,
    )
    
    failed_at = models.DateTimeField(
        _('failed at'),
        null=True,
        blank=True,
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
    )
    
    class Meta:
        verbose_name = _('payment')
        verbose_name_plural = _('payments')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment_id']),
            models.Index(fields=['reference_number']),
            models.Index(fields=['state']),
            models.Index(fields=['user', 'state']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f'Payment {self.reference_number} - {self.amount} {self.currency}'
    
    def save(self, *args, **kwargs):
        """Generate reference number and calculate amounts."""
        if not self.reference_number:
            self.reference_number = self._generate_reference_number()
        
        if self.amount and not self.platform_fee:
            self._calculate_fees()
        
        super().save(*args, **kwargs)
    
    def _generate_reference_number(self):
        """Generate unique payment reference number."""
        import random
        import string
        
        timestamp = timezone.now().strftime('%y%m%d%H%M%S')
        random_part = ''.join(random.choices(string.digits, k=6))
        return f'PAY-{timestamp}-{random_part}'
    
    def _calculate_fees(self):
        """Calculate platform fee and writer amount."""
        from decimal import Decimal
        
        platform_fee_percentage = getattr(settings, 'PLATFORM_FEE_PERCENTAGE', 20)
        fee_decimal = Decimal(platform_fee_percentage) / Decimal(100)
        
        self.platform_fee = self.amount * fee_decimal
        self.writer_amount = self.amount - self.platform_fee
    
    # State Transition Methods
    
    @transition(
        field=state,
        source='initiated',
        target='processing',
        permission=lambda user: True,  # System/background task
    )
    def start_processing(self):
        """Transition from initiated to processing."""
        self.processed_at = timezone.now()
    
    @transition(
        field=state,
        source='processing',
        target='held_in_escrow',
        conditions=[lambda instance: instance.fraud_check_passed],
        permission=lambda user: True,  # System/background task
    )
    def hold_in_escrow(self):
        """Transition from processing to held_in_escrow."""
        self.held_in_escrow_at = timezone.now()
        
        # Set escrow release date (default: 7 days after order completion)
        escrow_period = getattr(settings, 'ESCROW_HOLD_PERIOD', 7)
        self.escrow_held_until = timezone.now() + timezone.timedelta(days=escrow_period)
    
    @transition(
        field=state,
        source='held_in_escrow',
        target='released_to_wallet',
        permission=lambda user: user.is_staff,
    )
    def release_to_wallet(self):
        """Transition from held_in_escrow to released_to_wallet."""
        self.released_at = timezone.now()
        
        # Create wallet transaction for writer
        if self.order and self.order.writer:
            self._create_wallet_transaction()
    
    @transition(
        field=state,
        source=['held_in_escrow', 'processing'],
        target='refunded',
        permission=lambda user: user.is_staff,
    )
    def refund(self, refund_amount=None):
        """Transition to refunded."""
        self.refunded_at = timezone.now()
        
        if refund_amount and refund_amount < self.amount:
            self.amount = refund_amount  # Partial refund
    
    @transition(
        field=state,
        source=['processing', 'initiated'],
        target='failed',
        permission=lambda user: True,  # System/background task
    )
    def mark_as_failed(self, failure_reason=''):
        """Transition to failed."""
        self.failed_at = timezone.now()
        self.gateway_response = self.gateway_response or {}
        self.gateway_response['failure_reason'] = failure_reason
    
    @transition(
        field=state,
        source='initiated',
        target='cancelled',
        permission=lambda user: user == instance.user or user.is_staff,
    )
    def cancel(self):
        """Transition to cancelled."""
        pass  # State change only
    
    def _create_wallet_transaction(self):
        """Create wallet transaction for writer payment."""
        from apps.wallet.models import WalletTransaction
        
        WalletTransaction.objects.create(
            user=self.order.writer,
            amount=self.writer_amount,
            transaction_type='order_payment',
            payment=self,
            order=self.order,
            status='pending',
        )
    
    # Property Methods
    
    @property
    def is_in_escrow(self):
        """Check if payment is currently held in escrow."""
        return self.state == 'held_in_escrow'
    
    @property
    def is_released(self):
        """Check if payment has been released."""
        return self.state == 'released_to_wallet'
    
    @property
    def is_refunded(self):
        """Check if payment has been refunded."""
        return self.state == 'refunded'
    
    @property
    def can_be_released(self):
        """Check if escrow funds can be released."""
        if not self.is_in_escrow:
            return False
        
        # Check if order is completed
        if self.order:
            return self.order.state == 'completed'
        
        # Manual release by admin
        return True
    
    @property
    def time_in_escrow(self):
        """Calculate time spent in escrow."""
        if not self.held_in_escrow_at:
            return None
        
        end_time = self.released_at or timezone.now()
        return end_time - self.held_in_escrow_at
    
    @property
    def time_until_release(self):
        """Calculate time until automatic release."""
        if not self.is_in_escrow or not self.escrow_held_until:
            return None
        
        remaining = self.escrow_held_until - timezone.now()
        return max(remaining, timezone.timedelta(0))