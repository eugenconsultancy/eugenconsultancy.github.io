"""
Revision management models for controlled revision cycles.
Ensures limited, deadline-bound revisions with full audit trails.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django_fsm import FSMField, transition
from django.core.exceptions import ValidationError
import uuid


class RevisionRequest(models.Model):
    """
    Tracks revision requests from clients with state management.
    """
    # Revision states (simplified FSM for clarity)
    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='revision_requests')
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='client_revisions'
    )
    writer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL,  # Changed from CASCADE to SET_NULL
        related_name='writer_revisions',
        null=True, blank=True
    )
    
    # Revision details
    title = models.CharField(max_length=200)
    instructions = models.TextField(help_text="Detailed revision instructions from client")
    deadline = models.DateTimeField()
    max_revisions_allowed = models.PositiveSmallIntegerField(default=3)
    revisions_used = models.PositiveSmallIntegerField(default=0)
    
    # State management
    status = FSMField(
        default='requested',
        choices=STATUS_CHOICES,
        protected=True
    )
    
    # Tracking
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Audit trail
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_revisions'
    )
    last_modified = models.DateTimeField(auto_now=True)
    
    # Revision files
    original_files = models.ManyToManyField(
        'documents.Document',
        related_name='revision_originals',
        blank=True
    )
    revised_files = models.ManyToManyField(
        'documents.Document',
        related_name='revision_outputs',
        blank=True
    )
    
    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['deadline']),
            models.Index(fields=['client', 'status']),
        ]
        verbose_name = 'Revision Request'
        verbose_name_plural = 'Revision Requests'
    
    def __str__(self):
        return f"Revision for Order #{self.order.order_number} - {self.status}"
    
    def clean(self):
        """Validate revision constraints."""
        if self.deadline <= timezone.now():
            raise ValidationError("Deadline must be in the future")
        
        if self.revisions_used > self.max_revisions_allowed:
            raise ValidationError(
                f"Revisions used ({self.revisions_used}) exceed maximum allowed ({self.max_revisions_allowed})"
            )
    
    @transition(field=status, source='requested', target='in_progress')
    def start_revision(self, started_by=None):
        """Start working on the revision."""
        if not self.writer:
            raise ValidationError("Writer must be assigned before starting revision")
        
        self.started_at = timezone.now()
        self.save()
        return self
    
    @transition(field=status, source='in_progress', target='completed')
    def complete_revision(self, files=None):
        """Mark revision as completed."""
        if not files:
            raise ValidationError("Revised files must be uploaded")
        
        self.completed_at = timezone.now()
        self.revisions_used += 1
        self.save()
        return self
    
    @transition(field=status, source=['requested', 'in_progress'], target='cancelled')
    def cancel_revision(self):
        """Cancel the revision request."""
        self.save()
        return self
    
    def check_overdue(self):
        """Check if revision is overdue and update status."""
        if self.status in ['requested', 'in_progress'] and self.deadline < timezone.now():
            self.status = 'overdue'
            self.save()
            return True
        return False
    
    @property
    def is_overdue(self):
        """Check if revision is overdue."""
        return self.status == 'overdue' or (
            self.status in ['requested', 'in_progress'] and self.deadline < timezone.now()
        )
    
    @property
    def revisions_remaining(self):
        """Calculate remaining revisions."""
        return max(0, self.max_revisions_allowed - self.revisions_used)


class RevisionCycle(models.Model):
    """
    Tracks complete revision cycles for an order.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='revision_cycle')
    
    # Revision limits
    max_revisions_allowed = models.PositiveSmallIntegerField(default=3)
    revisions_used = models.PositiveSmallIntegerField(default=0)
    
    # Timing
    revision_period_days = models.PositiveSmallIntegerField(default=14)
    started_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField()
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Related requests
    revision_requests = models.ManyToManyField('RevisionRequest', related_name='cycles', blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['order', 'is_active']),
            models.Index(fields=['ends_at']),
        ]
        verbose_name = 'Revision Cycle'
        verbose_name_plural = 'Revision Cycles'
    
    def __str__(self):
        return f"Revision Cycle for Order #{self.order.order_number}"
    
    def clean(self):
        """Validate revision cycle constraints."""
        if self.revisions_used > self.max_revisions_allowed:
            raise ValidationError(
                f"Revisions used ({self.revisions_used}) exceed maximum allowed ({self.max_revisions_allowed})"
            )
    
    @property
    def revisions_remaining(self):
        """Calculate remaining revisions in cycle."""
        return max(0, self.max_revisions_allowed - self.revisions_used)
    
    @property
    def is_expired(self):
        """Check if revision cycle has expired."""
        return self.ends_at < timezone.now()
    
    def can_request_revision(self):
        """Check if a new revision can be requested."""
        return (
            self.is_active 
            and not self.is_expired 
            and self.revisions_remaining > 0
        )


class RevisionAuditLog(models.Model):
    """
    Audit trail for all revision activities.
    """
    ACTION_CHOICES = [
        ('requested', 'Revision Requested'),
        ('started', 'Revision Started'),
        ('file_uploaded', 'File Uploaded'),
        ('file_downloaded', 'File Downloaded'),
        ('completed', 'Revision Completed'),
        ('cancelled', 'Revision Cancelled'),
        ('deadline_extended', 'Deadline Extended'),
        ('status_changed', 'Status Changed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(RevisionRequest, on_delete=models.CASCADE, related_name='audit_logs')
    
    # Action details
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict, help_text="JSON details of the action")
    
    # Actor
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='revision_actions'
    )
    
    # Timestamp
    performed_at = models.DateTimeField(auto_now_add=True)
    
    # IP and user agent for security
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-performed_at']
        indexes = [
            models.Index(fields=['revision', 'performed_at']),
            models.Index(fields=['action', 'performed_at']),
        ]
        verbose_name = 'Revision Audit Log'
        verbose_name_plural = 'Revision Audit Logs'
    
    def __str__(self):
        return f"{self.action} on {self.revision} at {self.performed_at}"