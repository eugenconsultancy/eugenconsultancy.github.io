import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinLengthValidator
from django.urls import reverse
from ckeditor.fields import RichTextField
from taggit.managers import TaggableManager


class BlogCategory(models.Model):
    """Categories for blog posts"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(max_length=300, blank=True)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Blog Category"
        verbose_name_plural = "Blog Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('blog:category_detail', kwargs={'slug': self.slug})


class BlogPost(models.Model):
    """SEO-optimized blog posts"""
    
    class PostStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        UNDER_REVIEW = 'under_review', 'Under Review'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, validators=[MinLengthValidator(10)])
    slug = models.SlugField(max_length=220, unique=True)
    excerpt = models.TextField(max_length=300, help_text="Brief summary for preview")
    
    content = RichTextField(
        config_name='default',
        validators=[MinLengthValidator(300)],
        help_text="Minimum 300 characters"
    )
    
    featured_image = models.ImageField(
        upload_to='blog/images/%Y/%m/',
        blank=True,
        null=True,
        max_length=500
    )
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='blog_posts',
        limit_choices_to={'is_staff': True}  # Only staff can write blogs
    )
    
    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name='posts'
    )
    
    status = models.CharField(
        max_length=20,
        choices=PostStatus.choices,
        default=PostStatus.DRAFT
    )
    
    # SEO Fields
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(max_length=300, blank=True)
    meta_keywords = models.CharField(max_length=200, blank=True)
    
    # Reading Metrics
    reading_time_minutes = models.PositiveIntegerField(default=5)
    word_count = models.PositiveIntegerField(default=0)
    
    # Engagement Metrics
    view_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    
    # Technical Fields
    canonical_url = models.URLField(blank=True, null=True)
    structured_data = models.JSONField(blank=True, null=True)
    
    # Audit Fields
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_posts'
    )
    
    reviewed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tags
    tags = TaggableManager(blank=True)
    
    class Meta:
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', 'published_at']),
            models.Index(fields=['slug']),
            models.Index(fields=['view_count']),
        ]
        permissions = [
            ('can_publish_post', 'Can publish blog posts'),
            ('can_review_post', 'Can review blog posts'),
            ('can_manage_categories', 'Can manage blog categories'),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Auto-calculate word count
        self.word_count = len(self.content.split())
        self.reading_time_minutes = max(1, self.word_count // 200)  # 200 words per minute
        
        # Set published_at when status changes to published
        if self.status == self.PostStatus.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog:post_detail', kwargs={'slug': self.slug})

    def increment_view_count(self):
        """Atomically increment view count"""
        BlogPost.objects.filter(id=self.id).update(view_count=models.F('view_count') + 1)
        self.refresh_from_db()

    def is_published(self):
        return self.status == self.PostStatus.PUBLISHED and self.published_at <= timezone.now()


class BlogComment(models.Model):
    """Moderated comments on blog posts"""
    
    class CommentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        SPAM = 'spam', 'Marked as Spam'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    
    # Guest comment fields
    guest_name = models.CharField(max_length=100, blank=True)
    guest_email = models.EmailField(blank=True)
    
    content = models.TextField(max_length=1000, validators=[MinLengthValidator(10)])
    status = models.CharField(max_length=20, choices=CommentStatus.choices, default=CommentStatus.PENDING)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    is_reply = models.BooleanField(default=False)
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    upvotes = models.PositiveIntegerField(default=0)
    downvotes = models.PositiveIntegerField(default=0)
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_comments'
    )
    
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Blog Comment"
        verbose_name_plural = "Blog Comments"
        ordering = ['-created_at']
        permissions = [
            ('can_moderate_comments', 'Can moderate blog comments'),
        ]

    def __str__(self):
        return f"Comment by {self.display_name} on {self.post.title}"

    @property
    def display_name(self):
        return self.user.get_full_name() if self.user else self.guest_name

    def approve(self, reviewer):
        """Approve the comment"""
        self.status = self.CommentStatus.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()

    def reject(self, reviewer):
        """Reject the comment"""
        self.status = self.CommentStatus.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()


class SEOAuditLog(models.Model):
    """Log SEO audits and optimizations"""
    
    class AuditType(models.TextChoices):
        POST_CREATED = 'post_created', 'Post Created'
        POST_UPDATED = 'post_updated', 'Post Updated'
        SEO_CHECK = 'seo_check', 'SEO Check'
        OPTIMIZATION = 'optimization', 'Optimization Applied'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='seo_audits')
    audit_type = models.CharField(max_length=20, choices=AuditType.choices)
    
    # SEO Metrics
    readability_score = models.FloatField(null=True, blank=True)
    keyword_density = models.JSONField(null=True, blank=True)
    heading_structure = models.JSONField(null=True, blank=True)
    meta_score = models.FloatField(null=True, blank=True)
    
    # Issues and Recommendations
    issues_found = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    applied_fixes = models.JSONField(default=list, blank=True)
    
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "SEO Audit Log"
        verbose_name_plural = "SEO Audit Logs"
        ordering = ['-created_at']

    def __str__(self):
        return f"SEO Audit for {self.post.title} - {self.get_audit_type_display()}"


class BlogSubscription(models.Model):
    """Email subscriptions for blog updates"""
    
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    subscription_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Preferences
    receive_new_posts = models.BooleanField(default=True)
    receive_weekly_digest = models.BooleanField(default=False)
    categories = models.ManyToManyField(BlogCategory, blank=True)

    class Meta:
        verbose_name = "Blog Subscription"
        verbose_name_plural = "Blog Subscriptions"
        indexes = [
            models.Index(fields=['email', 'is_active']),
        ]

    def __str__(self):
        return self.email

    def unsubscribe(self):
        """Unsubscribe the user"""
        self.is_active = False
        self.unsubscribed_at = timezone.now()
        self.save()