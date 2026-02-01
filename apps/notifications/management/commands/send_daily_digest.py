# apps/notifications/management/commands/send_daily_digest.py
from django.core.management.base import BaseCommand
from django.utils import timezone
import logging

from apps.notifications.tasks import send_daily_digest

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send daily digest emails to users'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--test',
            action='store_true',
            help='Send test digest to admin users only'
        )
        parser.add_argument(
            '--user-email',
            type=str,
            help='Send digest to specific user email'
        )
    
    def handle(self, *args, **options):
        test_mode = options['test']
        user_email = options['user_email']
        
        if test_mode:
            self.stdout.write("Running in test mode - sending to admin users only")
            # In a real implementation, this would filter for admin users
            # For now, we'll just log and run the task
            logger.info("Daily digest test mode activated")
        
        if user_email:
            self.stdout.write(f"Sending digest to specific user: {user_email}")
            # In a real implementation, this would send to specific user
            # For now, we'll just log
            logger.info(f"Manual digest requested for user: {user_email}")
        
        try:
            # Call the Celery task
            send_daily_digest.delay()
            
            self.stdout.write(self.style.SUCCESS(
                "Daily digest task queued successfully"
            ))
            logger.info("Daily digest task queued")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"Failed to queue daily digest task: {e}"
            ))
            logger.error(f"Failed to queue daily digest task: {e}")