import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.utils import timezone
from django_fsm import FSMField, transition
from django.conf import settings


class Refund(models.Model):
    """Refund model for tracking payment refunds."""
    
    # State choices
    STATE_CHOICES = (
        ('requested', _('Requested')),
        ('under_review', _('Under Review')),
        ('approved', _('Approved')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('rejected', _('Rejected')),
        ('failed', _('Failed')),
    )
    
    # Refund type choices
    class RefundType(models.TextChoices):
        FULL = 'full', _('Full Refund')
        PARTIAL = 'partial', _('Partial Refund')
        COMPENSATION = 'compensation', _('Compensation')
    
    # Refund reason choices
    class RefundReason(models.TextChoices):
        QUALITY_ISSUE = 'quality_issue', _('Quality Issue')
        LATE_DELIVERY = 'late_delivery', _('Late Delivery')
        WRITER_MISCONDUCT = 'writer_misconduct', _('Writer Misconduct')
        CLIENT_REQUEST = 'client_request', _('Client Request')
        ORDER_CANCELLATION = 'order_cancellation', _('Order Cancellation')
        DISPUTE_RESOLUTION = 'dispute_resolution', _('Dispute Resolution')
        OTHER = 'other', _('Other')
    
    # Identification
    refund_id = models.UUIDField(
        _('refund ID'),
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    
    reference_number = models.CharField(
        _('reference number'),
        max_length=50,
        unique=True,
        db_index=True,
    )
    
    # Relationships
    # This works because Django resolves the string 'app_label.ModelName' later
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.CASCADE,
        related_name='refunds',
        verbose_name=_('payment')
    )
    
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='refunds',
        verbose_name=_('order')
    )
    
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='requested_refunds',
        verbose_name=_('requested by')
    )
    
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_refunds',
        verbose_name=_('processed by')
    )
    
    # Refund details
    refund_type = models.CharField(
        _('refund type'),
        max_length=20,
        choices=RefundType.choices,
        default=RefundType.FULL,
    )
    
    refund_reason = models.CharField(
        _('refund reason'),
        max_length=50,
        choices=RefundReason.choices,
        default=RefundReason.OTHER,
    )
    
    custom_reason = models.TextField(
        _('custom reason'),
        blank=True,
        help_text=_('Detailed explanation for refund request')
    )
    
    amount = models.DecimalField(
        _('amount'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text=_('Refund amount in platform currency')
    )
    
    original_amount = models.DecimalField(
        _('original amount'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text=_('Original payment amount')
    )
    
    currency = models.CharField(
        _('currency'),
        max_length=3,
        default='USD',
    )
    
    # State management
    state = FSMField(
        _('refund state'),
        default='requested',
        choices=STATE_CHOICES,
        protected=True,
    )
    
    # Processing details
    gateway_response = models.JSONField(
        _('gateway response'),
        null=True,
        blank=True,
    )
    
    gateway_transaction_id = models.CharField(
        _('gateway transaction ID'),
        max_length=100,
        blank=True,
    )
    
    # Review details
    review_notes = models.TextField(
        _('review notes'),
        blank=True,
        help_text=_('Admin notes regarding refund decision')
    )
    
    rejection_reason = models.TextField(
        _('rejection reason'),
        blank=True,
        help_text=_('Reason for refund rejection if applicable')
    )
    
    # Timestamps
    requested_at = models.DateTimeField(
        _('requested at'),
        auto_now_add=True,
    )
    
    reviewed_at = models.DateTimeField(
        _('reviewed at'),
        null=True,
        blank=True,
    )
    
    approved_at = models.DateTimeField(
        _('approved at'),
        null=True,
        blank=True,
    )
    
    processing_started_at = models.DateTimeField(
        _('processing started at'),
        null=True,
        blank=True,
    )
    
    completed_at = models.DateTimeField(
        _('completed at'),
        null=True,
        blank=True,
    )
    
    rejected_at = models.DateTimeField(
        _('rejected at'),
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
        verbose_name = _('refund')
        verbose_name_plural = _('refunds')
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['refund_id']),
            models.Index(fields=['reference_number']),
            models.Index(fields=['state']),
            models.Index(fields=['payment', 'state']),
            models.Index(fields=['requested_by', 'state']),
        ]
    
    def __str__(self):
        return f'Refund {self.reference_number} - {self.amount} {self.currency}'
    
    def save(self, *args, **kwargs):
        """Generate reference number."""
        if not self.reference_number:
            self.reference_number = self._generate_reference_number()
        
        if not self.original_amount and self.payment:
            self.original_amount = self.payment.amount
        
        super().save(*args, **kwargs)
    
    def _generate_reference_number(self):
        """Generate unique refund reference number."""
        import random
        import string
        
        timestamp = timezone.now().strftime('%y%m%d%H%M%S')
        random_part = ''.join(random.choices(string.digits, k=6))
        return f'REF-{timestamp}-{random_part}'
    
    # State Transition Methods
    
    @transition(
        field=state,
        source='requested',
        target='under_review',
        permission=lambda user: user.is_staff,
    )
    def start_review(self, admin_user):
        """Transition from requested to under_review."""
        self.reviewed_at = timezone.now()
        self.processed_by = admin_user
    
    @transition(
        field=state,
        source='under_review',
        target='approved',
        permission=lambda user: user.is_staff,
    )
    def approve(self, admin_user, notes=''):
        """Transition from under_review to approved."""
        self.approved_at = timezone.now()
        self.processed_by = admin_user
        self.review_notes = notes
    
    @transition(
        field=state,
        source='under_review',
        target='rejected',
        permission=lambda user: user.is_staff,
    )
    def reject(self, admin_user, reason):
        """Transition from under_review to rejected."""
        self.rejected_at = timezone.now()
        self.processed_by = admin_user
        self.rejection_reason = reason
    
    @transition(
        field=state,
        source='approved',
        target='processing',
        permission=lambda user: user.is_staff,
    )
    def start_processing(self):
        """Transition from approved to processing."""
        self.processing_started_at = timezone.now()
    
    @transition(
        field=state,
        source='processing',
        target='completed',
        permission=lambda user: True,  # System/background task
    )
    def complete(self, gateway_response=None):
        """Transition from processing to completed."""
        self.completed_at = timezone.now()
        self.gateway_response = gateway_response
        
        # Update payment state
        self.payment.refund(self.amount)
        self.payment.save()
    
    @transition(
        field=state,
        source='processing',
        target='failed',
        permission=lambda user: True,  # System/background task
    )
    def mark_as_failed(self, failure_reason=''):
        """Transition from processing to failed."""
        self.failed_at = timezone.now()
        self.gateway_response = self.gateway_response or {}
        self.gateway_response['failure_reason'] = failure_reason
    
    # Property Methods
    
    @property
    def refund_percentage(self):
        """Calculate refund percentage of original amount."""
        if self.original_amount == 0:
            return 0
        return (self.amount / self.original_amount) * 100
    
    @property
    def is_full_refund(self):
        """Check if refund is for full amount."""
        return self.refund_type == 'full' or self.amount == self.original_amount
    
    @property
    def processing_time(self):
        """Calculate total processing time."""
        if not self.requested_at:
            return None
        
        end_time = self.completed_at or self.rejected_at or timezone.now()
        return end_time - self.requested_at
    
    @property
    def can_be_processed(self):
        """Check if refund can be processed."""
        if self.state != 'approved':
            return False
        
        # Check if payment is in a state that allows refund
        valid_payment_states = ['held_in_escrow', 'processing']
        return self.payment.state in valid_payment_states
    
    def validate_amount(self):
        """Validate refund amount against payment."""
        from django.core.exceptions import ValidationError
        
        if self.amount > self.original_amount:
            raise ValidationError(
                f'Refund amount ({self.amount}) cannot exceed original amount ({self.original_amount})'
            )
        
        # Check if partial refunds are allowed for the reason
        if (self.refund_type == 'partial' and 
            self.refund_reason in ['writer_misconduct', 'order_cancellation']):
            # These typically require full refunds
            raise ValidationError(
                f'{self.get_refund_reason_display()} requires a full refund'
            )