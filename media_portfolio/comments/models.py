from django.db import models
from django.core.validators import EmailValidator
from media_portfolio.core.models import BaseModel
from media_portfolio.media.models import MediaItem


class Comment(BaseModel):
    """
    Model for comments on media items with threading support
    """
    media_item = models.ForeignKey(
        MediaItem,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies'
    )
    
    # Commenter info
    name = models.CharField(max_length=100)
    email = models.EmailField(validators=[EmailValidator()])
    website = models.URLField(blank=True, help_text="Optional: Your website or portfolio")
    
    # Comment content
    content = models.TextField()
    
    # Moderation
    is_approved = models.BooleanField(
        default=False,
        help_text="Approve for public display"
    )
    is_spam = models.BooleanField(default=False)
    is_featured = models.BooleanField(
        default=False,
        help_text="Feature this comment as a testimonial"
    )
    
    # Tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # For testimonials
    can_use_as_testimonial = models.BooleanField(
        default=False,
        help_text="Can I feature this comment on my site?"
    )
    testimonial_approved = models.BooleanField(
        default=False,
        help_text="Approved to use as testimonial"
    )

    class Meta:
        app_label = 'comments'
        verbose_name = "Comment"
        verbose_name_plural = "Comments"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['media_item', 'is_approved']),
            models.Index(fields=['is_featured']),
        ]

    def __str__(self):
        return f"Comment by {self.name} on {self.media_item.title}"

    def get_replies(self):
        """Get all approved replies to this comment"""
        return self.replies.filter(is_approved=True)


class Testimonial(BaseModel):
    """
    Featured testimonials (can be from media_portfolio.comments or standalone)
    """
    name = models.CharField(max_length=100)
    title = models.CharField(max_length=200, blank=True, help_text="e.g., Client, Art Director")
    company = models.CharField(max_length=200, blank=True)
    
    # Optional link to original comment
    source_comment = models.OneToOneField(
        Comment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='testimonial'
    )
    
    # Testimonial content
    content = models.TextField()
    
    # Optional photo
    photo = models.ImageField(
        upload_to='testimonials/',
        blank=True,
        null=True
    )
    
    # Display
    rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        default=5,
        help_text="Rating out of 5"
    )
    featured = models.BooleanField(default=True)

    class Meta:
        app_label = 'comments'
        verbose_name = "Testimonial"
        verbose_name_plural = "Testimonials"

    def __str__(self):
        return f"Testimonial from {self.name}"