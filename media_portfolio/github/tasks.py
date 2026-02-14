import logging
from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task
def sync_github_repos(username):
    """
    Celery task to sync GitHub repositories
    """
    try:
        from django.conf import settings
        
        if not username and settings.GITHUB_USERNAME:
            username = settings.GITHUB_USERNAME
        
        if not username:
            logger.error("GitHub username not configured")
            return
        
        call_command('sync_github', username=username, token=settings.GITHUB_TOKEN)
        logger.info(f"GitHub sync completed for {username}")
        
    except Exception as e:
        logger.error(f"GitHub sync task failed: {str(e)}")
        raise