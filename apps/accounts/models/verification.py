from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django_fsm import FSMField, transition
from django.conf import settings


class WriterVerificationStatus(models.Model):
    """Finite State Machine for writer verification process."""
    
    STATE_CHOICES = (
        ('registered', _('Registered')),
        ('profile_completed', _('Profile Completed')),
        ('documents_submitted', _('Documents Submitted')),
        ('under_admin_review', _('Under Admin Review')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('revision_required', _('Revision Required')),
    )
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_status',
        verbose_name=_('user')
    )
    
    state = FSMField(
        _('verification state'),
        default='registered',
        choices=STATE_CHOICES,
        protected=True,  # Prevents direct state changes
    )
    
    # Verification tracking
    profile_completed_at = models.DateTimeField(
        _('profile completed at'),
        null=True,
        blank=True,
    )
    
    documents_submitted_at = models.DateTimeField(
        _('documents submitted at'),
        null=True,
        blank=True,
    )
    
    review_started_at = models.DateTimeField(
        _('review started at'),
        null=True,
        blank=True,
    )
    
    review_completed_at = models.DateTimeField(
        _('review completed at'),
        null=True,
        blank=True,
    )
    
    # Decision details
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_verifications',
        verbose_name=_('approved by')
    )
    
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_verifications',
        verbose_name=_('rejected by')
    )
    
    rejection_reason = models.TextField(
        _('rejection reason'),
        blank=True,
        help_text=_('Detailed reason for rejection')
    )
    
    revision_notes = models.TextField(
        _('revision notes'),
        blank=True,
        help_text=_('Notes on what needs to be revised')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
    )
    
    class Meta:
        verbose_name = _('writer verification status')
        verbose_name_plural = _('writer verification statuses')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['state']),
            models.Index(fields=['user', 'state']),
        ]
    
    def __str__(self):
        return f'Verification: {self.user.email} - {self.get_state_display()}'
    
    # State transitions
    
    @transition(
        field=state,
        source='registered',
        target='profile_completed',
        conditions=[lambda instance: instance.user.writer_profile.status == 'active'],
        permission=lambda user: user == instance.user,
    )
    def complete_profile(self):
        """Transition from registered to profile_completed."""
        self.profile_completed_at = timezone.now()
    
    @transition(
        field=state,
        source='profile_completed',
        target='documents_submitted',
        conditions=[
            lambda instance: instance.user.documents.filter(
                status='verified'
            ).count() >= 3  # Minimum 3 verified documents
        ],
        permission=lambda user: user == instance.user,
    )
    def submit_documents(self):
        """Transition from profile_completed to documents_submitted."""
        self.documents_submitted_at = timezone.now()
    
    @transition(
        field=state,
        source='documents_submitted',
        target='under_admin_review',
        permission=lambda user: user.is_staff,
    )
    def start_admin_review(self, admin_user):
        """Transition from documents_submitted to under_admin_review."""
        self.review_started_at = timezone.now()
    
    @transition(
        field=state,
        source='under_admin_review',
        target='approved',
        permission=lambda user: user.is_staff,
    )
    def approve(self, admin_user):
        """Transition from under_admin_review to approved."""
        self.review_completed_at = timezone.now()
        self.approved_by = admin_user
        
        # Activate writer profile
        writer_profile = self.user.writer_profile
        writer_profile.status = 'active'
        writer_profile.activated_at = timezone.now()
        writer_profile.save()
    
    @transition(
        field=state,
        source='under_admin_review',
        target='rejected',
        permission=lambda user: user.is_staff,
    )
    def reject(self, admin_user, reason):
        """Transition from under_admin_review to rejected."""
        self.review_completed_at = timezone.now()
        self.rejected_by = admin_user
        self.rejection_reason = reason
        
        # Disable writer profile
        writer_profile = self.user.writer_profile
        writer_profile.status = 'disabled'
        writer_profile.save()
    
    @transition(
        field=state,
        source=['rejected', 'revision_required'],
        target='documents_submitted',
        permission=lambda user: user == instance.user,
    )
    def resubmit(self):
        """Transition from rejected/revision_required to documents_submitted."""
        self.documents_submitted_at = timezone.now()
        self.review_started_at = None
        self.review_completed_at = None
        self.rejection_reason = ''
        self.revision_notes = ''
    
    @transition(
        field=state,
        source='under_admin_review',
        target='revision_required',
        permission=lambda user: user.is_staff,
    )
    def require_revision(self, admin_user, notes):
        """Transition from under_admin_review to revision_required."""
        self.revision_notes = notes
    
    @property
    def can_submit_documents(self):
        """Check if user can submit documents."""
        return self.state == 'profile_completed'
    
    @property
    def is_approved(self):
        """Check if writer is approved."""
        return self.state == 'approved'
    
    @property
    def is_rejected(self):
        """Check if writer is rejected."""
        return self.state == 'rejected'
    
    @property
    def needs_revision(self):
        """Check if writer needs to revise submission."""
        return self.state == 'revision_required'
    
    @property
    def time_in_review(self):
        """Calculate time spent in review."""
        if not self.review_started_at:
            return None
        
        end_time = self.review_completed_at or timezone.now()
        return end_time - self.review_started_at