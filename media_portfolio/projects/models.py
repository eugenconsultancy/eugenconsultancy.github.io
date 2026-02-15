import os
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from media_portfolio.core.models import BaseModel
from media_portfolio.categories.models import Category


def project_thumbnail_path(instance, filename):
    """Generate upload path for project thumbnails"""
    ext = filename.split('.')[-1].lower()
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    return f'projects/thumbnails/{instance.slug}_{timestamp}.{ext}'


class Project(BaseModel):
    """
    Enhanced Project model for portfolio with comprehensive fields
    """
    DIFFICULTY_LEVELS = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert'),
    ]

    # Basic Information
    title = models.CharField(max_length=200, help_text="The catchy name of the project")
    slug = models.SlugField(max_length=250, unique=True, help_text="SEO-friendly URL")
    short_summary = models.CharField(
        max_length=300,
        help_text="1-2 sentence 'elevator pitch' for quick scanning"
    )
    description = models.TextField(blank=True, help_text="Full project description")
    
    # Project Details
    problem_statement = models.TextField(
        blank=True,
        help_text="The 'Why'—what specific problem were you trying to solve?"
    )
    solution = models.TextField(
        blank=True,
        help_text="The 'How'—details on your architecture and logic"
    )
    
    # Technical Information
    technical_stack = models.JSONField(
        default=list,
        blank=True,
        help_text='List of languages and frameworks (e.g., ["Python", "React", "Django"])'
    )
    api_integrations = models.JSONField(
        default=list,
        blank=True,
        help_text='External services used (e.g., ["Stripe", "OpenAI", "Twilio"])'
    )
    
    # Media
    thumbnail = models.ImageField(
        upload_to=project_thumbnail_path,
        help_text="High-quality screenshot of the UI"
    )
    thumbnail_webp = models.ImageField(
        upload_to='projects/thumbnails/webp/',
        blank=True,
        null=True,
        help_text="Optimized WebP version"
    )
    thumbnail_blur = models.ImageField(
        upload_to='projects/thumbnails/blur/',
        blank=True,
        null=True,
        help_text="Blurred placeholder for lazy loading"
    )
    
    # Links
    github_url = models.URLField(
        blank=True,
        help_text="Link to the repository for code review"
    )
    live_demo_url = models.URLField(
        blank=True,
        help_text="Hosted version of the site"
    )
    documentation_url = models.URLField(
        blank=True,
        help_text="Link to project documentation"
    )
    
    # Categories and Organization
    categories = models.ManyToManyField(
        Category,
        related_name='projects',
        blank=True,
        help_text="Project categories"
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated tags"
    )
    
    # Difficulty and Highlighting
    difficulty_level = models.CharField(
        max_length=20,
        choices=DIFFICULTY_LEVELS,
        default='intermediate',
        help_text="Helps recruiters see your growth from Basic to Advanced"
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Highlight this project at the top of the UI"
    )
    performance_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Lighthouse performance metric"
    )
    
    # Stats
    stars_count = models.IntegerField(
        default=0,
        help_text="GitHub stars count (auto-updated)"
    )
    forks_count = models.IntegerField(
        default=0,
        help_text="GitHub forks count (auto-updated)"
    )
    last_github_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time GitHub stats were synced"
    )
    
    # Display Control
    is_published = models.BooleanField(default=True)
    published_date = models.DateTimeField(default=timezone.now)
    view_count = models.IntegerField(default=0, editable=False)
    
    # Copyright
    copyright_notice = models.CharField(
        max_length=200,
        default="© All Rights Reserved"
    )
    license = models.CharField(
        max_length=20,
        choices=[
            ('copyright', 'All Rights Reserved'),
            ('mit', 'MIT License'),
            ('apache', 'Apache License 2.0'),
            ('gpl', 'GNU GPL v3'),
            ('bsd', 'BSD License'),
            ('public', 'Public Domain'),
        ],
        default='copyright'
    )

    class Meta:
        app_label = 'projects'
        verbose_name = "Project"
        verbose_name_plural = "Projects"
        ordering = ['-is_featured', '-performance_score', '-published_date']
        indexes = [
            models.Index(fields=['difficulty_level', 'is_published']),
            models.Index(fields=['-stars_count']),
            models.Index(fields=['-published_date']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Auto-generate slug if not provided
        if not self.slug:
            self.slug = slugify(self.title)
        
        # Ensure unique slug
        original_slug = self.slug
        counter = 1
        while Project.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
            self.slug = f"{original_slug}-{counter}"
            counter += 1
        
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('projects:detail', args=[self.slug])

    @property
    def tag_list(self):
        """Return tags as list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []

    def increment_view_count(self):
        """Increment view count"""
        self.view_count += 1
        self.save(update_fields=['view_count'])


class ProjectLike(BaseModel):
    """
    Model for tracking project likes
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='likes'
    )
    session_key = models.CharField(max_length=40, blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        app_label = 'projects'
        verbose_name = "Project Like"
        verbose_name_plural = "Project Likes"
        unique_together = ['project', 'session_key']
        indexes = [
            models.Index(fields=['project', 'session_key']),
        ]

    def __str__(self):
        return f"Like for {self.project.title}"


class ProjectComment(BaseModel):
    """
    Model for comments on projects
    """
    project = models.ForeignKey(
        Project,
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
    email = models.EmailField()
    website = models.URLField(blank=True, help_text="Optional")
    
    # Comment content
    content = models.TextField()
    
    # Moderation
    is_approved = models.BooleanField(default=False)
    is_spam = models.BooleanField(default=False)
    
    # Tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        app_label = 'projects'
        verbose_name = "Project Comment"
        verbose_name_plural = "Project Comments"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'is_approved']),
        ]

    def __str__(self):
        return f"Comment by {self.name} on {self.project.title}"