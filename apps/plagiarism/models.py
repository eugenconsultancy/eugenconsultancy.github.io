"""
Plagiarism detection models for academic integrity.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid
import json


class PlagiarismCheck(models.Model):
    """
    Tracks plagiarism checks for orders.
    Admin-only access to reports.
    """
    SOURCE_CHOICES = [
        ('copyscape', 'Copyscape'),
        ('turnitin', 'Turnitin'),
        ('grammarly', 'Grammarly'),
        ('quetext', 'Quetext'),
        ('internal', 'Internal Scanner'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='plagiarism_checks')
    
    # Check details
    source = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    
    # Results (stored as JSON for flexibility)
    similarity_score = models.FloatField(null=True, blank=True, help_text="Overall similarity percentage")
    word_count = models.IntegerField(null=True, blank=True)
    character_count = models.IntegerField(null=True, blank=True)
    
    # Detailed results
    raw_result = models.JSONField(default=dict, help_text="Raw API response or scan result")
    highlights = models.JSONField(default=dict, help_text="Highlighted matching sections")
    sources = models.JSONField(default=list, help_text="List of matched sources")
    
    # File reference
    checked_file = models.ForeignKey(
        'documents.Document',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plagiarism_checks'
    )
    
    # Security flags
    is_sensitive = models.BooleanField(
        default=False,
        help_text="Mark if report contains sensitive information"
    )
    
    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Audit
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='requested_plagiarism_checks'
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_plagiarism_checks'
    )
    
    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['similarity_score']),
            models.Index(fields=['requested_at']),
        ]
        verbose_name = 'Plagiarism Check'
        verbose_name_plural = 'Plagiarism Checks'
    
    def __str__(self):
        return f"Plagiarism check for Order #{self.order.order_number}"
    
    @property
    def is_completed(self):
        """Check if plagiarism check is completed."""
        return self.status == 'completed'
    
    @property
    def risk_level(self):
        """Determine risk level based on similarity score."""
        if not self.similarity_score:
            return 'unknown'
        
        if self.similarity_score < 10:
            return 'low'
        elif self.similarity_score < 25:
            return 'medium'
        elif self.similarity_score < 50:
            return 'high'
        else:
            return 'critical'
    
    @property
    def formatted_result(self):
        """Format result for display."""
        if not self.is_completed:
            return {"status": self.status}
        
        return {
            "score": self.similarity_score,
            "risk_level": self.risk_level,
            "word_count": self.word_count,
            "character_count": self.character_count,
            "sources_count": len(self.sources),
            "highlights_summary": f"{len(self.highlights.get('matches', []))} matches found"
        }


class PlagiarismReport(models.Model):
    """
    Detailed plagiarism reports (admin-only access).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plagiarism_check = models.OneToOneField(
        PlagiarismCheck, 
        on_delete=models.CASCADE, 
        related_name='detailed_report'
    )
    
    # Report content
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    detailed_analysis = models.JSONField(default=dict)
    
    # Security
    access_key = models.CharField(max_length=64, unique=True, editable=False)
    is_encrypted = models.BooleanField(default=True)
    
    # Access control
    view_count = models.IntegerField(default=0)
    last_viewed = models.DateTimeField(null=True, blank=True)
    last_viewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['plagiarism_check']),
            models.Index(fields=['access_key']),
            models.Index(fields=['expires_at']),
        ]
        verbose_name = 'Plagiarism Report'
        verbose_name_plural = 'Plagiarism Reports'
    
    def __str__(self):
        return f"Report for {self.plagiarism_check}"
    
    def save(self, *args, **kwargs):
        """Generate access key if not set."""
        if not self.access_key:
            import secrets
            self.access_key = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if report has expired."""
        if self.expires_at:
            return self.expires_at < timezone.now()
        return False
    
    def increment_view(self, user=None):
        """Increment view count and update last viewed."""
        self.view_count += 1
        self.last_viewed = timezone.now()
        if user:
            self.last_viewed_by = user
        self.save()


class PlagiarismPolicy(models.Model):
    """
    Platform plagiarism policies and thresholds.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    
    # Thresholds
    warning_threshold = models.FloatField(
        default=10.0,
        help_text="Similarity percentage that triggers warning"
    )
    action_threshold = models.FloatField(
        default=25.0,
        help_text="Similarity percentage that requires action"
    )
    rejection_threshold = models.FloatField(
        default=50.0,
        help_text="Similarity percentage that triggers rejection"
    )
    
    # Actions
    warning_action = models.JSONField(
        default=dict,
        help_text="Action to take at warning threshold"
    )
    critical_action = models.JSONField(
        default=dict,
        help_text="Action to take at critical threshold"
    )
    
    # Scope
    order_types = models.JSONField(
        default=list,
        help_text="Order types this policy applies to"
    )
    client_tiers = models.JSONField(
        default=list,
        help_text="Client tiers this policy applies to"
    )
    
    # Active status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Plagiarism Policy'
        verbose_name_plural = 'Plagiarism Policies'
    
    def __str__(self):
        return self.name
    
    def evaluate(self, similarity_score):
        """
        Evaluate a similarity score against this policy.
        
        Returns:
            Dictionary with evaluation results
        """
        if similarity_score < self.warning_threshold:
            return {
                'level': 'acceptable',
                'message': 'Plagiarism level within acceptable limits',
                'action_required': False
            }
        elif similarity_score < self.action_threshold:
            return {
                'level': 'warning',
                'message': f'Warning: Similarity score ({similarity_score}%) exceeds warning threshold',
                'action_required': True,
                'action': self.warning_action
            }
        elif similarity_score < self.rejection_threshold:
            return {
                'level': 'critical',
                'message': f'Critical: Similarity score ({similarity_score}%) exceeds action threshold',
                'action_required': True,
                'action': self.critical_action
            }
        else:
            return {
                'level': 'reject',
                'message': f'Reject: Similarity score ({similarity_score}%) exceeds rejection threshold',
                'action_required': True,
                'action': {'type': 'reject_order', 'notify_admin': True}
            }