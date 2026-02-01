from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid


class Review(models.Model):
    """Customer review for completed orders"""
    RATING_CHOICES = [
        (1, '1 Star - Very Poor'),
        (2, '2 Stars - Poor'),
        (3, '3 Stars - Average'),
        (4, '4 Stars - Good'),
        (5, '5 Stars - Excellent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='review'
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews_given'
    )
    writer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews_received'
    )
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    
    # Quality metrics (1-5 scale)
    communication_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    timeliness_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    quality_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    adherence_rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    
    # Moderation fields
    is_approved = models.BooleanField(default=False)
    is_flagged = models.BooleanField(default=False)
    flagged_reason = models.TextField(blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderated_reviews'
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    is_verified = models.BooleanField(default=True)  # Order was completed
    is_edited = models.BooleanField(default=False)
    edit_reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    helpful_count = models.PositiveIntegerField(default=0)
    report_count = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        indexes = [
            models.Index(fields=['writer', 'rating']),
            models.Index(fields=['is_approved', 'is_active']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'customer'],
                name='unique_order_customer_review'
            ),
            models.CheckConstraint(
                check=models.Q(rating__gte=1) & models.Q(rating__lte=5),
                name='rating_range_check'
            ),
        ]
    
    def __str__(self):
        return f"Review for Order #{self.order.order_number}: {self.rating} stars"
    
    @property
    def average_quality_score(self):
        """Calculate average of all quality metrics"""
        scores = []
        if self.communication_rating:
            scores.append(self.communication_rating)
        if self.timeliness_rating:
            scores.append(self.timeliness_rating)
        if self.quality_rating:
            scores.append(self.quality_rating)
        if self.adherence_rating:
            scores.append(self.adherence_rating)
        
        if scores:
            return sum(scores) / len(scores)
        return None
    
    @property
    def is_negative(self):
        """Check if review is negative (≤ 2 stars)"""
        return self.rating <= 2
    
    def approve(self, moderator):
        """Approve review for public display"""
        self.is_approved = True
        self.is_flagged = False
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.save()
    
    def flag(self, reason):
        """Flag review for moderation"""
        self.is_flagged = True
        self.flagged_reason = reason
        self.is_approved = False
        self.save()
    
    def increment_helpful(self):
        """Increment helpful count"""
        self.helpful_count = models.F('helpful_count') + 1
        self.save(update_fields=['helpful_count'])
    
    def increment_report(self):
        """Increment report count"""
        self.report_count = models.F('report_count') + 1
        self.save(update_fields=['report_count'])


class ReviewResponse(models.Model):
    """Writer response to a review"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.OneToOneField(
        Review,
        on_delete=models.CASCADE,
        related_name='response'
    )
    writer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_responses'
    )
    response_text = models.TextField()
    
    # Moderation
    is_approved = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = 'Review Response'
        verbose_name_plural = 'Review Responses'
    
    def __str__(self):
        return f"Response to Review {self.review.id}"
    
    def approve(self):
        """Approve response"""
        self.is_approved = True
        self.save()


class ReviewFlag(models.Model):
    """User reports/flags on reviews"""
    FLAG_REASONS = [
        ('inappropriate', 'Inappropriate Content'),
        ('spam', 'Spam or Advertisement'),
        ('fake', 'Fake Review'),
        ('harassment', 'Harassment or Abuse'),
        ('irrelevant', 'Irrelevant to Service'),
        ('conflict', 'Conflict of Interest'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='flags'
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_flags'
    )
    reason = models.CharField(max_length=20, choices=FLAG_REASONS)
    description = models.TextField(blank=True)
    
    # Resolution
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_flags'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Review Flag'
        verbose_name_plural = 'Review Flags'
        constraints = [
            models.UniqueConstraint(
                fields=['review', 'reporter'],
                name='unique_review_reporter_flag'
            ),
        ]
    
    def __str__(self):
        return f"Flag on Review {self.review.id} by {self.reporter.email}"
    
    def resolve(self, admin_user, notes):
        """Resolve flag"""
        self.is_resolved = True
        self.resolved_by = admin_user
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()


class WriterRatingSummary(models.Model):
    """Aggregated rating summary for writers"""
    writer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rating_summary'
    )
    
    # Overall ratings
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    total_reviews = models.PositiveIntegerField(default=0)
    
    # Rating distribution
    rating_5 = models.PositiveIntegerField(default=0)
    rating_4 = models.PositiveIntegerField(default=0)
    rating_3 = models.PositiveIntegerField(default=0)
    rating_2 = models.PositiveIntegerField(default=0)
    rating_1 = models.PositiveIntegerField(default=0)
    
    # Quality metrics averages
    avg_communication = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    avg_timeliness = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    avg_quality = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    avg_adherence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    
    # Performance metrics
    positive_review_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    recent_rating_trend = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00
    )
    
    # Timestamps
    last_review_at = models.DateTimeField(null=True, blank=True)
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Writer Rating Summary'
        verbose_name_plural = 'Writer Rating Summaries'
    
    def __str__(self):
        return f"Rating Summary: {self.writer.email} ({self.average_rating}★)"
    
    @property
    def positive_reviews(self):
        """Count positive reviews (4-5 stars)"""
        return self.rating_5 + self.rating_4
    
    @property
    def negative_reviews(self):
        """Count negative reviews (1-2 stars)"""
        return self.rating_1 + self.rating_2
    
    @property
    def rating_percentages(self):
        """Get rating percentages"""
        if self.total_reviews == 0:
            return {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        
        return {
            5: (self.rating_5 / self.total_reviews) * 100,
            4: (self.rating_4 / self.total_reviews) * 100,
            3: (self.rating_3 / self.total_reviews) * 100,
            2: (self.rating_2 / self.total_reviews) * 100,
            1: (self.rating_1 / self.total_reviews) * 100,
        }
    
    def update_summary(self):
        """Update summary from actual reviews"""
        from django.db.models import Avg, Count, Q
        
        reviews = Review.objects.filter(
            writer=self.writer,
            is_approved=True,
            is_active=True
        )
        
        # Calculate averages
        aggregates = reviews.aggregate(
            avg_rating=Avg('rating'),
            avg_communication=Avg('communication_rating'),
            avg_timeliness=Avg('timeliness_rating'),
            avg_quality=Avg('quality_rating'),
            avg_adherence=Avg('adherence_rating'),
            total=Count('id')
        )
        
        self.average_rating = aggregates['avg_rating'] or 0
        self.avg_communication = aggregates['avg_communication'] or 0
        self.avg_timeliness = aggregates['avg_timeliness'] or 0
        self.avg_quality = aggregates['avg_quality'] or 0
        self.avg_adherence = aggregates['avg_adherence'] or 0
        self.total_reviews = aggregates['total'] or 0
        
        # Get rating distribution
        self.rating_5 = reviews.filter(rating=5).count()
        self.rating_4 = reviews.filter(rating=4).count()
        self.rating_3 = reviews.filter(rating=3).count()
        self.rating_2 = reviews.filter(rating=2).count()
        self.rating_1 = reviews.filter(rating=1).count()
        
        # Calculate positive percentage
        positive_count = self.rating_5 + self.rating_4
        self.positive_review_percentage = (
            (positive_count / self.total_reviews * 100) if self.total_reviews > 0 else 0
        )
        
        # Get last review date
        last_review = reviews.order_by('-created_at').first()
        self.last_review_at = last_review.created_at if last_review else None
        
        self.save()