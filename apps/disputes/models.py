"""
Dispute resolution models for handling order disputes.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django_fsm import FSMField, transition
from django.core.exceptions import ValidationError
import uuid
import json


class Dispute(models.Model):
    """
    Tracks order disputes with state management and resolution workflow.
    """
    # Dispute states
    STATUS_CHOICES = [
        ('opened', 'Opened'),
        ('under_review', 'Under Review'),
        ('awaiting_response', 'Awaiting Response'),
        ('evidence_review', 'Evidence Review'),
        ('resolution_proposed', 'Resolution Proposed'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Dispute reasons
    REASON_CHOICES = [
        ('quality_issue', 'Quality Issue'),
        ('deadline_missed', 'Deadline Missed'),
        ('plagiarism', 'Plagiarism'),
        ('not_as_described', 'Not as Described'),
        ('incomplete_work', 'Incomplete Work'),
        ('communication_issue', 'Communication Issue'),
        ('refund_request', 'Refund Request'),
        ('other', 'Other'),
    ]
    
    # Resolution types
    RESOLUTION_CHOICES = [
        ('full_refund', 'Full Refund'),
        ('partial_refund', 'Partial Refund'),
        ('revision_required', 'Revision Required'),
        ('new_writer_assigned', 'New Writer Assigned'),
        ('compensation', 'Compensation'),
        ('in_favor_of_client', 'In Favor of Client'),
        ('in_favor_of_writer', 'In Favor of Writer'),
        ('mutual_agreement', 'Mutual Agreement'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='disputes')
    
    # Parties
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='opened_disputes'
    )
    against_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='disputes_against'
    )
    
    # Dispute details
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Resolution
    resolution_type = models.CharField(
        max_length=50, 
        choices=RESOLUTION_CHOICES, 
        null=True, 
        blank=True
    )
    resolution_details = models.TextField(blank=True)
    resolution_proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposed_resolutions'
    )
    
    # State management
    status = FSMField(
        default='opened',
        choices=STATUS_CHOICES,
        protected=True
    )
    
    # Financial aspects
    requested_refund_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    approved_refund_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    # Snapshots (JSON for flexibility)
    order_snapshot = models.JSONField(default=dict, help_text="Order state at dispute opening")
    messages_snapshot = models.JSONField(default=list, help_text="Relevant messages snapshot")
    files_snapshot = models.JSONField(default=list, help_text="Relevant files snapshot")
    
    # Timestamps
    opened_at = models.DateTimeField(auto_now_add=True)
    under_review_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Admin assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_disputes',
        limit_choices_to={'is_staff': True}
    )
    
    # Priority
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # SLA tracking
    sla_deadline = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-opened_at']
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['opened_by', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['priority', 'status']),
            models.Index(fields=['sla_deadline']),
        ]
        verbose_name = 'Dispute'
        verbose_name_plural = 'Disputes'
    
    def __str__(self):
        return f"Dispute #{self.id.hex[:8]} - Order #{self.order.order_number}"
    
    def clean(self):
        """Validate dispute constraints."""
        if self.opened_by == self.against_user:
            raise ValidationError("Cannot open dispute against yourself")
        
        # Validate order status allows disputes
        if self.order.status not in ['delivered', 'in_progress', 'completed']:
            raise ValidationError(f"Disputes cannot be opened for orders in status: {self.order.status}")
    
    @transition(field=status, source='opened', target='under_review')
    def assign_for_review(self, assigned_to):
        """Assign dispute to admin for review."""
        self.assigned_to = assigned_to
        self.under_review_at = timezone.now()
        self.sla_deadline = timezone.now() + timezone.timedelta(hours=72)  # 72-hour SLA
        self.save()
        return self
    
    @transition(field=status, source='under_review', target='awaiting_response')
    def request_response(self):
        """Request response from the other party."""
        self.first_response_at = self.first_response_at or timezone.now()
        self.save()
        return self
    
    @transition(field=status, source='awaiting_response', target='evidence_review')
    def review_evidence(self):
        """Move to evidence review phase."""
        self.save()
        return self
    
    @transition(field=status, source='evidence_review', target='resolution_proposed')
    def propose_resolution(self, resolution_type, resolution_details, proposed_by):
        """Propose a resolution."""
        self.resolution_type = resolution_type
        self.resolution_details = resolution_details
        self.resolution_proposed_by = proposed_by
        self.save()
        return self
    
    @transition(field=status, source='resolution_proposed', target='resolved')
    def resolve(self):
        """Mark dispute as resolved."""
        self.resolved_at = timezone.now()
        self.save()
        return self
    
    @transition(field=status, source='*', target='escalated')
    def escalate(self):
        """Escalate dispute to higher authority."""
        self.save()
        return self
    
    @transition(field=status, source='*', target='cancelled')
    def cancel(self):
        """Cancel the dispute."""
        self.save()
        return self
    
    @property
    def is_overdue(self):
        """Check if dispute SLA is overdue."""
        if self.sla_deadline and self.status not in ['resolved', 'cancelled']:
            return timezone.now() > self.sla_deadline
        return False
    
    @property
    def sla_status(self):
        """Get SLA status."""
        if not self.sla_deadline:
            return 'not_set'
        
        if self.is_overdue:
            return 'overdue'
        
        hours_remaining = (self.sla_deadline - timezone.now()).total_seconds() / 3600
        if hours_remaining < 24:
            return 'urgent'
        elif hours_remaining < 48:
            return 'warning'
        else:
            return 'ok'


class DisputeEvidence(models.Model):
    """
    Evidence submitted for disputes.
    """
    EVIDENCE_TYPES = [
        ('message', 'Message'),
        ('file', 'File'),
        ('screenshot', 'Screenshot'),
        ('testimonial', 'Testimonial'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='evidences')
    
    # Evidence details
    evidence_type = models.CharField(max_length=20, choices=EVIDENCE_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # File or content
    file = models.ForeignKey(
        'documents.Document',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    content = models.TextField(blank=True, help_text="Text content or URL")
    
    # Submitted by
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_evidence'
    )
    
    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    # Admin notes
    admin_notes = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_evidence'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['dispute', 'evidence_type']),
            models.Index(fields=['submitted_by', 'submitted_at']),
        ]
        verbose_name = 'Dispute Evidence'
        verbose_name_plural = 'Dispute Evidences'
    
    def __str__(self):
        return f"Evidence for {self.dispute} - {self.evidence_type}"


class DisputeMessage(models.Model):
    """
    Messages within dispute resolution process.
    """
    MESSAGE_TYPES = [
        ('internal', 'Internal (Admin Only)'),
        ('external', 'External (Visible to Parties)'),
        ('resolution', 'Resolution Proposal'),
        ('update', 'Status Update'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='messages')
    
    # Message content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='external')
    content = models.TextField()
    
    # Sender
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dispute_messages'
    )
    
    # Visibility
    visible_to_client = models.BooleanField(default=True)
    visible_to_writer = models.BooleanField(default=True)
    visible_to_admin = models.BooleanField(default=True)
    
    # Timestamps
    sent_at = models.DateTimeField(auto_now_add=True)
    
    # Attachments
    attachments = models.ManyToManyField(
        'documents.Document',
        related_name='dispute_message_attachments',
        blank=True
    )
    
    # Read receipts
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='read_dispute_messages',
        blank=True
    )
    
    class Meta:
        ordering = ['sent_at']
        indexes = [
            models.Index(fields=['dispute', 'sent_at']),
            models.Index(fields=['sent_by', 'sent_at']),
        ]
        verbose_name = 'Dispute Message'
        verbose_name_plural = 'Dispute Messages'
    
    def __str__(self):
        return f"Message in {self.dispute} by {self.sent_by}"


class DisputeResolutionLog(models.Model):
    """
    Log of all dispute resolution activities.
    """
    ACTION_CHOICES = [
        ('opened', 'Dispute Opened'),
        ('assigned', 'Assigned to Admin'),
        ('evidence_submitted', 'Evidence Submitted'),
        ('message_sent', 'Message Sent'),
        ('resolution_proposed', 'Resolution Proposed'),
        ('resolution_accepted', 'Resolution Accepted'),
        ('resolution_rejected', 'Resolution Rejected'),
        ('escalated', 'Escalated'),
        ('resolved', 'Resolved'),
        ('cancelled', 'Cancelled'),
        ('refund_initiated', 'Refund Initiated'),
        ('sla_breached', 'SLA Breached'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='resolution_logs')
    
    # Action details
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict, help_text="JSON details of the action")
    
    # Performed by
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='dispute_actions'
    )
    
    # Timestamp
    performed_at = models.DateTimeField(auto_now_add=True)
    
    # IP and user agent
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-performed_at']
        indexes = [
            models.Index(fields=['dispute', 'performed_at']),
            models.Index(fields=['action', 'performed_at']),
        ]
        verbose_name = 'Dispute Resolution Log'
        verbose_name_plural = 'Dispute Resolution Logs'
    
    def __str__(self):
        return f"{self.action} on {self.dispute} at {self.performed_at}"