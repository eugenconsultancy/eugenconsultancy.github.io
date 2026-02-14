import os
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.files.base import ContentFile
from django.conf import settings
from .models import Project
from media_portfolio.media.utils import (
    optimize_image_to_webp,
    create_blurred_placeholder
)

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Project)
def project_pre_save(sender, instance, **kwargs):
    """
    Handle pre-save operations for projects
    """
    # Check if thumbnail is being updated
    if instance.pk:
        try:
            old_instance = Project.objects.get(pk=instance.pk)
            if old_instance.thumbnail != instance.thumbnail:
                instance._thumbnail_changed = True
            else:
                instance._thumbnail_changed = False
        except Project.DoesNotExist:
            instance._thumbnail_changed = False
    else:
        instance._thumbnail_changed = True if instance.thumbnail else False


@receiver(post_save, sender=Project)
def project_post_save(sender, instance, created, **kwargs):
    """
    Handle post-save operations: image optimization, WebP conversion, blur placeholders
    """
    if not hasattr(instance, '_thumbnail_changed') or not instance._thumbnail_changed:
        return
    
    if not instance.thumbnail:
        return
    
    try:
        # Get the thumbnail path
        thumbnail_path = instance.thumbnail.path
        
        # Check if file exists
        if not os.path.exists(thumbnail_path):
            logger.error(f"Thumbnail file not found: {thumbnail_path}")
            return
        
        # 1. Optimize and convert to WebP
        webp_content = optimize_image_to_webp(thumbnail_path, quality=80)
        if webp_content:
            # Generate WebP filename
            webp_filename = f"{os.path.splitext(os.path.basename(thumbnail_path))[0]}.webp"
            
            # Save WebP version
            instance.thumbnail_webp.save(
                webp_filename,
                ContentFile(webp_content),
                save=False
            )
            logger.info(f"Generated WebP for project {instance.id}: {webp_filename}")
        
        # 2. Create blurred placeholder
        blur_content = create_blurred_placeholder(thumbnail_path, blur_radius=10, size=(20, 20))
        if blur_content:
            # Generate blur filename
            blur_filename = f"{os.path.splitext(os.path.basename(thumbnail_path))[0]}_blur.jpg"
            
            # Save blur version
            instance.thumbnail_blur.save(
                blur_filename,
                ContentFile(blur_content),
                save=False
            )
            logger.info(f"Generated blur placeholder for project {instance.id}")
        
        # Save the instance with new images
        if instance.thumbnail_webp or instance.thumbnail_blur:
            instance.save(update_fields=['thumbnail_webp', 'thumbnail_blur'])
        
    except Exception as e:
        logger.error(f"Error in project image optimization for {instance.id}: {str(e)}")