from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings


class WriterProfile(models.Model):
    """Writer profile with qualifications and specialization."""
    
    class EducationLevel(models.TextChoices):
        BACHELORS = 'bachelors', _("Bachelor's Degree")
        MASTERS = 'masters', _("Master's Degree")
        PHD = 'phd', _('PhD')
        PROFESSOR = 'professor', _('Professor')
    
    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        UNDER_REVIEW = 'under_review', _('Under Review')
        ACTIVE = 'active', _('Active')
        SUSPENDED = 'suspended', _('Suspended')
        DISABLED = 'disabled', _('Disabled')
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='writer_profile',
        verbose_name=_('user')
    )
    
    # Personal Information
    bio = models.TextField(
        _('biography'),
        max_length=2000,
        blank=True,
        help_text=_('Brief professional biography (max 2000 characters)')
    )
    
    education_level = models.CharField(
        _('highest education level'),
        max_length=20,
        choices=EducationLevel.choices,
        blank=True,
    )
    
    institution = models.CharField(
        _('institution'),
        max_length=255,
        blank=True,
        help_text=_('University or institution name')
    )
    
    graduation_year = models.PositiveIntegerField(
        _('graduation year'),
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1900),
            MaxValueValidator(2100),
        ]
    )
    
    # Professional Information
    years_of_experience = models.PositiveIntegerField(
        _('years of experience'),
        default=0,
        validators=[MaxValueValidator(50)]
    )
    
    hourly_rate = models.DecimalField(
        _('hourly rate'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text=_('Hourly rate in platform currency')
    )
    
    total_earnings = models.DecimalField(
        _('total earnings'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Total earnings from completed orders')
    )
    
    completed_orders = models.PositiveIntegerField(
        _('completed orders'),
        default=0
    )
    
    average_rating = models.DecimalField(
        _('average rating'),
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)]
    )
    
    # Specialization
    specialization = models.TextField(
        _('specialization'),
        blank=True,
        help_text=_('Areas of expertise (comma-separated)')
    )
    
    # Availability
    is_available = models.BooleanField(
        _('available for assignments'),
        default=True
    )
    
    max_orders = models.PositiveIntegerField(
        _('maximum concurrent orders'),
        default=3,
        help_text=_('Maximum number of orders writer can handle simultaneously')
    )
    
    current_orders = models.PositiveIntegerField(
        _('current orders'),
        default=0
    )
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    
    # Timestamps
    profile_completed_at = models.DateTimeField(
        _('profile completed at'),
        null=True,
        blank=True,
    )
    
    activated_at = models.DateTimeField(
        _('activated at'),
        null=True,
        blank=True,
    )
    
    last_activity = models.DateTimeField(
        _('last activity'),
        auto_now=True,
    )
    
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
    )
    
    class Meta:
        verbose_name = _('writer profile')
        verbose_name_plural = _('writer profiles')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['education_level']),
            models.Index(fields=['average_rating']),
            models.Index(fields=['is_available']),
        ]
    
    def __str__(self):
        return f'Writer Profile: {self.user.email}'
    
    @property
    def can_accept_orders(self):
        """Check if writer can accept new orders."""
        return (
            self.status == self.Status.ACTIVE
            and self.is_available
            and self.current_orders < self.max_orders
        )
    
    @property
    def success_rate(self):
        """Calculate writer's success rate."""
        if self.completed_orders == 0:
            return 0
        return (self.completed_orders / (self.completed_orders + 5)) * 100
    
    def update_rating(self, new_rating):
        """Update average rating when new review is added."""
        if self.average_rating == 0:
            self.average_rating = new_rating
        else:
            self.average_rating = (
                (self.average_rating * self.completed_orders) + new_rating
            ) / (self.completed_orders + 1)
        self.save()