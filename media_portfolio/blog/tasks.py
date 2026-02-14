import logging
from celery import shared_task
from django.core.management import call_command
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task
def sync_blog_posts(username=None):
    """
    Celery task to sync blog posts from Dev.to
    """
    try:
        if not username and settings.DEVTO_USERNAME:
            username = settings.DEVTO_USERNAME
        
        if not username:
            # Try Medium as fallback
            if settings.MEDIUM_USERNAME:
                call_command('sync_blog', source='medium', username=settings.MEDIUM_USERNAME)
                logger.info(f"Medium sync completed for {settings.MEDIUM_USERNAME}")
            else:
                logger.error("No blog username configured")
            return
        
        call_command('sync_blog', source='devto', username=username)
        logger.info(f"Dev.to sync completed for {username}")
        
    except Exception as e:
        logger.error(f"Blog sync task failed: {str(e)}")
        raise