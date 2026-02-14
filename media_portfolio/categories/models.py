from django.db import models
from media_portfolio.core.models import BaseModel


class Category(BaseModel):
    """
    Category for media items with type classification
    """
    CATEGORY_TYPES = [
        ('medium', 'Medium (Photography/Video/3D/Design)'),
        ('genre', 'Genre (Portrait/Landscape/Abstract/Street)'),
        ('technique', 'Technique (Digital/Film/Analog/Timelapse)'),
        ('subject', 'Subject (People/Nature/Architecture/Products)'),
        ('collection', 'Collection/Series'),
        ('client', 'Client Work'),
        ('personal', 'Personal Projects'),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPES)
    description = models.TextField(blank=True)
    
    # Visual representation
    cover_image = models.ImageField(
        upload_to='categories/covers/',
        blank=True,
        null=True,
        help_text="Cover image for this category"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Font Awesome icon class (e.g., 'fa-camera')"
    )
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    
    # Parent-child relationship for nested categories
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children'
    )

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['category_type', 'sort_order', 'name']

    def __str__(self):
        return f"{self.get_category_type_display()}: {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def media_count(self):
        """Get count of media items in this category"""
        return self.media_items.count()