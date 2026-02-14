from django.db import models
from django.core.validators import EmailValidator
from media_portfolio.core.models import BaseModel
from media_portfolio.media.models import MediaItem


class Inquiry(BaseModel):
    """
    Model for client inquiries and messages
    """
    INQUIRY_TYPES = [
        ('general', 'General Question'),
        ('license', 'Licensing Request'),
        ('print', 'Print Purchase'),
        ('commission', 'Commission Work'),
        ('collaboration', 'Collaboration'),
        ('interview', 'Interview Request'),
        ('workshop', 'Workshop/Teaching'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('new', 'New'),
        ('read', 'Read'),
        ('replied', 'Replied'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]
    
    # Inquiry type
    inquiry_type = models.CharField(max_length=20, choices=INQUIRY_TYPES)
    
    # Related media (if inquiring about specific work)
    media_item = models.ForeignKey(
        MediaItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inquiries'
    )
    
    # Contact info
    name = models.CharField(max_length=100)
    email = models.EmailField(validators=[EmailValidator()])
    phone = models.CharField(max_length=20, blank=True)
    company = models.CharField(max_length=200, blank=True)
    
    # Subject and message
    subject = models.CharField(max_length=200)
    message = models.TextField()
    
    # Additional details based on inquiry type
    usage_type = models.CharField(
        max_length=200,
        blank=True,
        help_text="How will the media be used? (for licensing)"
    )
    deadline = models.DateField(
        null=True,
        blank=True,
        help_text="Project deadline"
    )
    budget_range = models.CharField(
        max_length=100,
        blank=True,
        help_text="Budget range for the project"
    )
    
    # Tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Response tracking
    responded_at = models.DateTimeField(null=True, blank=True)
    response_notes = models.TextField(blank=True, help_text="Internal notes about response")
    
    # Legal consent
    accepted_terms = models.BooleanField(default=False)
    accepted_privacy = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Inquiry"
        verbose_name_plural = "Inquiries"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['inquiry_type', 'status']),
        ]

    def __str__(self):
        return f"{self.get_inquiry_type_display()}: {self.subject} - {self.name}"