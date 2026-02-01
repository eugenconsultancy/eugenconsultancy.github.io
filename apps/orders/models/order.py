from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django_fsm import FSMField, transition
from django.conf import settings


class Order(models.Model):
    """Order model with FSM-driven workflow."""
    
    # State choices (ordered by workflow)
    STATE_CHOICES = (
        ('draft', _('Draft')),
        ('paid', _('Paid')),
        ('assigned', _('Assigned')),
        ('in_progress', _('In Progress')),
        ('delivered', _('Delivered')),
        ('revision_requested', _('Revision Requested')),
        ('in_revision', _('In Revision')),
        ('completed', _('Completed')),
        ('disputed', _('Disputed')),
        ('refunded', _('Refunded')),
        ('cancelled', _('Cancelled')),
    )
    
    class UrgencyLevel(models.TextChoices):
        STANDARD = 'standard', _('Standard (14 days)')
        URGENT = 'urgent', _('Urgent (7 days)')
        VERY_URGENT = 'very_urgent', _('Very Urgent (3 days)')
        EMERGENCY = 'emergency', _('Emergency (24 hours)')
    
    class AcademicLevel(models.TextChoices):
        HIGH_SCHOOL = 'high_school', _('High School')
        UNDERGRADUATE = 'undergraduate', _('Undergraduate')
        BACHELORS = 'bachelors', _("Bachelor's")
        MASTERS = 'masters', _("Master's")
        PHD = 'phd', _('PhD')
        PROFESSIONAL = 'professional', _('Professional')
    
    # Basic Information
    order_number = models.CharField(
        _('order number'),
        max_length=20,
        unique=True,
        db_index=True,
    )
    
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_orders',
        verbose_name=_('client')
    )
    
    writer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='writer_orders',
        verbose_name=_('writer')
    )
    
    # Order Details
    title = models.CharField(
        _('order title'),
        max_length=500,
    )
    
    description = models.TextField(
        _('description'),
        max_length=5000,
        help_text=_('Detailed description of the order requirements')
    )
    
    subject = models.CharField(
        _('subject area'),
        max_length=200,
        help_text=_('e.g., Computer Science, Business, Psychology')
    )
    
    academic_level = models.CharField(
        _('academic level'),
        max_length=20,
        choices=AcademicLevel.choices,
        default=AcademicLevel.UNDERGRADUATE,
    )
    
    # Requirements
    pages = models.PositiveIntegerField(
        _('number of pages'),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    
    words = models.PositiveIntegerField(
        _('number of words'),
        default=275,
        validators=[MinValueValidator(100), MaxValueValidator(50000)]
    )
    
    sources = models.PositiveIntegerField(
        _('number of sources'),
        default=3,
        validators=[MaxValueValidator(100)]
    )
    
    formatting_style = models.CharField(
        _('formatting style'),
        max_length=50,
        default='APA',
        help_text=_('e.g., APA, MLA, Chicago, Harvard')
    )
    
    # Timeline
    urgency = models.CharField(
        _('urgency level'),
        max_length=20,
        choices=UrgencyLevel.choices,
        default=UrgencyLevel.STANDARD,
    )
    
    deadline = models.DateTimeField(
        _('deadline'),
        help_text=_('Final deadline for order completion')
    )
    
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
    )
    
    # Financial
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Total price in platform currency')
    )
    
    writer_payment = models.DecimalField(
        _('writer payment'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text=_('Amount to be paid to writer')
    )
    
    platform_fee = models.DecimalField(
        _('platform fee'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        help_text=_('Platform commission')
    )
    
    # State Management
    state = FSMField(
        _('order state'),
        default='draft',
        choices=STATE_CHOICES,
        protected=True,
    )
    
    # Timestamps for state transitions
    paid_at = models.DateTimeField(
        _('paid at'),
        null=True,
        blank=True,
    )
    
    assigned_at = models.DateTimeField(
        _('assigned at'),
        null=True,
        blank=True,
    )
    
    started_at = models.DateTimeField(
        _('started at'),
        null=True,
        blank=True,
    )
    
    delivered_at = models.DateTimeField(
        _('delivered at'),
        null=True,
        blank=True,
    )
    
    completed_at = models.DateTimeField(
        _('completed at'),
        null=True,
        blank=True,
    )
    
    cancelled_at = models.DateTimeField(
        _('cancelled at'),
        null=True,
        blank=True,
    )
    
    # Quality & Revision
    revision_count = models.PositiveIntegerField(
        _('revision count'),
        default=0,
        validators=[MaxValueValidator(10)]
    )
    
    max_revisions = models.PositiveIntegerField(
        _('maximum revisions'),
        default=3,
    )
    
    # Dispute & Refund
    dispute_reason = models.TextField(
        _('dispute reason'),
        blank=True,
    )
    
    refund_amount = models.DecimalField(
        _('refund amount'),
        max_digits=10,
        decimal_places=2,
        default=0.00,
    )
    
    refunded_at = models.DateTimeField(
        _('refunded at'),
        null=True,
        blank=True,
    )
    
    # Admin
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_orders',
        verbose_name=_('assigned by')
    )
    
    admin_notes = models.TextField(
        _('admin notes'),
        blank=True,
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
    )
    
    class Meta:
        verbose_name = _('order')
        verbose_name_plural = _('orders')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['state']),
            models.Index(fields=['client', 'state']),
            models.Index(fields=['writer', 'state']),
            models.Index(fields=['deadline']),
            models.Index(fields=['academic_level']),
            models.Index(fields=['subject']),
        ]
    
    def __str__(self):
        return f'Order #{self.order_number}: {self.title[:50]}'
    
    def save(self, *args, **kwargs):
        """Generate order number on creation."""
        if not self.order_number:
            self.order_number = self._generate_order_number()
        
        # Calculate writer payment and platform fee
        if self.price and not self.writer_payment:
            self._calculate_payments()
        
        super().save(*args, **kwargs)
    
    def _generate_order_number(self):
        """Generate unique order number."""
        import uuid
        import random
        import string
        
        # Format: EB-{timestamp}-{random}
        timestamp = timezone.now().strftime('%y%m%d')
        random_part = ''.join(random.choices(string.digits, k=6))
        return f'EB-{timestamp}-{random_part}'
    
    def _calculate_payments(self):
        """Calculate writer payment and platform fee."""
        from decimal import Decimal
        
        platform_fee_percentage = getattr(settings, 'PLATFORM_FEE_PERCENTAGE', 20)
        fee_decimal = Decimal(platform_fee_percentage) / Decimal(100)
        
        self.platform_fee = self.price * fee_decimal
        self.writer_payment = self.price - self.platform_fee
    
    # State Transition Methods
    
    @transition(
        field=state,
        source='draft',
        target='paid',
        conditions=[lambda instance: instance.price > 0],
        permission=lambda user: user == instance.client or user.is_staff,
    )
    def mark_as_paid(self, payment=None):
        """Transition from draft to paid."""
        self.paid_at = timezone.now()
        
        if payment:
            self.payment = payment
    
    @transition(
        field=state,
        source='paid',
        target='assigned',
        conditions=[
            lambda instance: instance.writer is not None,
            lambda instance: instance.writer.writer_profile.can_accept_orders,
        ],
        permission=lambda user: user.is_staff,
    )
    def assign_to_writer(self, admin_user, writer):
        """Transition from paid to assigned."""
        self.writer = writer
        self.assigned_by = admin_user
        self.assigned_at = timezone.now()
        
        # Update writer's current order count
        writer.writer_profile.current_orders += 1
        writer.writer_profile.save()
    
    @transition(
        field=state,
        source='assigned',
        target='in_progress',
        permission=lambda user: user == instance.writer,
    )
    def start_work(self):
        """Transition from assigned to in_progress."""
        self.started_at = timezone.now()
    
    @transition(
        field=state,
        source=['in_progress', 'in_revision'],
        target='delivered',
        permission=lambda user: user == instance.writer,
    )
    def deliver(self):
        """Transition from in_progress/in_revision to delivered."""
        self.delivered_at = timezone.now()
    
    @transition(
        field=state,
        source='delivered',
        target='revision_requested',
        conditions=[lambda instance: instance.revision_count < instance.max_revisions],
        permission=lambda user: user == instance.client,
    )
    def request_revision(self, reason=''):
        """Transition from delivered to revision_requested."""
        self.revision_count += 1
    
    @transition(
        field=state,
        source='revision_requested',
        target='in_revision',
        permission=lambda user: user == instance.writer,
    )
    def accept_revision(self):
        """Transition from revision_requested to in_revision."""
        pass  # State change only
    
    @transition(
        field=state,
        source='delivered',
        target='completed',
        conditions=[lambda instance: instance.revision_count == 0],
        permission=lambda user: user == instance.client,
    )
    def complete_without_revision(self):
        """Transition from delivered to completed (no revision needed)."""
        self.completed_at = timezone.now()
        
        # Release payment to writer
        self._release_writer_payment()
    
    @transition(
        field=state,
        source='delivered',
        target='completed',
        conditions=[lambda instance: instance.revision_count > 0],
        permission=lambda user: user == instance.client,
    )
    def complete_after_revision(self):
        """Transition from delivered to completed (after revisions)."""
        self.completed_at = timezone.now()
        
        # Release payment to writer
        self._release_writer_payment()
        
        # Update writer stats
        self._update_writer_stats()
    
    @transition(
        field=state,
        source=['paid', 'assigned', 'in_progress'],
        target='cancelled',
        permission=lambda user: user == instance.client or user.is_staff,
    )
    def cancel(self, reason=''):
        """Transition to cancelled."""
        self.cancelled_at = timezone.now()
        
        # Refund client
        self._process_refund()
        
        # Update writer's order count if assigned
        if self.writer and self.state == 'assigned':
            self.writer.writer_profile.current_orders = max(
                0, self.writer.writer_profile.current_orders - 1
            )
            self.writer.writer_profile.save()
    
    @transition(
        field=state,
        source=['delivered', 'in_revision', 'revision_requested'],
        target='disputed',
        permission=lambda user: user == instance.client,
    )
    def dispute(self, reason):
        """Transition to disputed."""
        self.dispute_reason = reason
    
    @transition(
        field=state,
        source='disputed',
        target='refunded',
        permission=lambda user: user.is_staff,
    )
    def refund(self, amount, admin_user):
        """Transition from disputed to refunded."""
        self.refund_amount = amount
        self.refunded_at = timezone.now()
        self.refunded_by = admin_user
        
        # Process refund
        self._process_refund()
    
    def _release_writer_payment(self):
        """Release payment to writer's wallet."""
        from apps.wallet.models import WalletTransaction
        
        if self.writer and self.writer_payment > 0:
            WalletTransaction.objects.create(
                user=self.writer,
                amount=self.writer_payment,
                transaction_type='order_completion',
                order=self,
                status='pending',
            )
    
    def _process_refund(self):
        """Process refund to client."""
        from apps.payments.services.escrow_service import EscrowService
        
        EscrowService.refund_order(self.id, self.refund_amount)
    
    def _update_writer_stats(self):
        """Update writer statistics upon order completion."""
        if self.writer:
            profile = self.writer.writer_profile
            profile.completed_orders += 1
            profile.current_orders = max(0, profile.current_orders - 1)
            profile.total_earnings += self.writer_payment
            profile.save()
    
    # Property Methods
    
    @property
    def is_overdue(self):
        """Check if order is overdue."""
        return timezone.now() > self.deadline
    
    @property
    def time_remaining(self):
        """Calculate time remaining until deadline."""
        remaining = self.deadline - timezone.now()
        return max(remaining, timezone.timedelta(0))
    
    @property
    def progress_percentage(self):
        """Calculate order progress percentage based on state."""
        progress_map = {
            'draft': 0,
            'paid': 10,
            'assigned': 20,
            'in_progress': 40,
            'delivered': 80,
            'revision_requested': 85,
            'in_revision': 90,
            'completed': 100,
            'disputed': 50,
            'refunded': 100,
            'cancelled': 100,
        }
        return progress_map.get(self.state, 0)
    
    @property
    def can_request_revision(self):
        """Check if client can request revision."""
        return (
            self.state == 'delivered'
            and self.revision_count < self.max_revisions
        )
    
    @property
    def can_be_assigned(self):
        """Check if order can be assigned to a writer."""
        return (
            self.state == 'paid'
            and not self.writer
        )