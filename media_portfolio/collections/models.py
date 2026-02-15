from django.db import models
from django.utils import timezone
from media_portfolio.core.models import BaseModel
from media_portfolio.media.models import MediaItem


class Collection(BaseModel):
    """
    Model for grouping media items into collections/series
    """
    COLLECTION_TYPES = [
        ('series', 'Series'),
        ('exhibition', 'Exhibition'),
        ('project', 'Project'),
        ('client', 'Client Work'),
        ('personal', 'Personal'),
        ('award', 'Award Winning'),
    ]
    
    LAYOUT_CHOICES = [
        ('grid', 'Grid'),
        ('masonry', 'Masonry'),
        ('slideshow', 'Slideshow'),
        ('carousel', 'Carousel'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=250, unique=True)
    collection_type = models.CharField(max_length=20, choices=COLLECTION_TYPES, default='series')
    description = models.TextField(blank=True)
    
    # Visual representation
    cover_image = models.ImageField(
        upload_to='collections/covers/',
        blank=True,
        null=True,
        help_text="Cover image for the collection"
    )
    
    # Media items in this collection
    media_items = models.ManyToManyField(
        MediaItem,
        through='CollectionItem',
        related_name='collections',
        blank=True
    )
    
    # Display options
    layout = models.CharField(
        max_length=20,
        choices=LAYOUT_CHOICES,
        default='grid'
    )
    is_published = models.BooleanField(default=True)
    published_date = models.DateTimeField(default=timezone.now)
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    
    # Featured
    featured = models.BooleanField(default=False)
    
    class Meta:
        app_label = 'collections'
        verbose_name = "Collection"
        verbose_name_plural = "Collections"
        ordering = ['-featured', '-published_date']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('collections:detail', args=[self.slug])


class CollectionItem(models.Model):
    """
    Through model for collection items with ordering and custom captions
    """
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    media_item = models.ForeignKey(MediaItem, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    custom_caption = models.TextField(blank=True, help_text="Override the media item's caption for this collection")
    
    class Meta:
        app_label = 'collections'
        ordering = ['order']
        unique_together = ['collection', 'media_item']

    def __str__(self):
        return f"{self.collection.title} - {self.media_item.title}"