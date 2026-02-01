# apps/notifications/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.notifications.models import (
    Notification,
    NotificationPreference,
    EmailTemplate
)

User = get_user_model()


class NotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@test.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        # Create notification preference
        self.preference = NotificationPreference.objects.create(
            user=self.user,
            email_enabled=True,
            push_enabled=True
        )
        
        # Create test notification
        self.notification = Notification.objects.create(
            user=self.user,
            title='Test Notification',
            message='This is a test notification',
            notification_type='info',
            channels='in_app',
            priority=2
        )
        
        self.api_client = APIClient()
    
    def test_notification_creation(self):
        """Test notification creation."""
        self.assertEqual(self.notification.user, self.user)
        self.assertEqual(self.notification.title, 'Test Notification')
        self.assertFalse(self.notification.is_read)
        self.assertFalse(self.notification.is_sent)
    
    def test_mark_as_read(self):
        """Test marking notification as read."""
        self.assertFalse(self.notification.is_read)
        self.assertIsNone(self.notification.read_at)
        
        self.notification.mark_as_read()
        
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)
        self.assertIsNotNone(self.notification.read_at)
    
    def test_notification_preferences(self):
        """Test notification preferences."""
        self.assertTrue(self.preference.email_enabled)
        self.assertTrue(self.preference.push_enabled)
        self.assertFalse(self.preference.sms_enabled)
        
        # Test category preferences
        self.assertTrue(
            self.preference.is_category_enabled('order_updates', 'email')
        )
    
    def test_quiet_hours(self):
        """Test quiet hours functionality."""
        # Set quiet hours
        self.preference.quiet_hours_enabled = True
        self.preference.quiet_hours_start = timezone.datetime.strptime('22:00', '%H:%M').time()
        self.preference.quiet_hours_end = timezone.datetime.strptime('08:00', '%H:%M').time()
        self.preference.save()
        
        # Test during quiet hours
        quiet_time = timezone.datetime.strptime('23:00', '%H:%M').time()
        with self.subTest("During quiet hours"):
            # We'd mock timezone.now() to return a time during quiet hours
            pass
        
        # Test outside quiet hours
        non_quiet_time = timezone.datetime.strptime('12:00', '%H:%M').time()
        with self.subTest("Outside quiet hours"):
            # We'd mock timezone.now() to return a time outside quiet hours
            pass
    
    def test_notification_api(self):
        """Test notification API endpoints."""
        self.api_client.force_authenticate(user=self.user)
        
        # Get notifications
        response = self.api_client.get('/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # Mark as read
        response = self.api_client.post(
            f'/notifications/{self.notification.id}/read/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check notification is now read
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)
        
        # Get unread notifications (should be empty)
        response = self.api_client.get('/notifications/unread/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
    
    def test_email_template(self):
        """Test email template functionality."""
        template = EmailTemplate.objects.create(
            name='test_template',
            template_type='system',
            subject='Test Email',
            body_template='Hello {{user_name}}!',
            plain_text_template='Hello {{user_name}}!',
            is_active=True
        )
        
        self.assertEqual(template.name, 'test_template')
        self.assertTrue(template.is_active)
        self.assertEqual(template.version, 1)
        
        # Test template content
        self.assertEqual(template.get_template_content(), 'Hello {{user_name}}!')


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='service@test.com',
            password='testpass123'
        )
    
    def test_create_notification(self):
        """Test creating notification via service."""
        from apps.notifications.services import NotificationService
        
        notification = NotificationService.create_notification(
            user=self.user,
            title='Service Test',
            message='Notification created via service',
            notification_type='success',
            channels='in_app',
            priority=3
        )
        
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.title, 'Service Test')
        self.assertEqual(notification.notification_type, 'success')
        self.assertEqual(notification.priority, 3)
    
    def test_mark_all_as_read(self):
        """Test marking all notifications as read."""
        from apps.notifications.services import NotificationService
        
        # Create multiple notifications
        for i in range(5):
            Notification.objects.create(
                user=self.user,
                title=f'Notification {i}',
                message=f'Message {i}',
                notification_type='info'
            )
        
        # Check all are unread
        self.assertEqual(Notification.objects.filter(is_read=False).count(), 5)
        
        # Mark all as read
        count = NotificationService.mark_all_as_read(self.user)
        
        self.assertEqual(count, 5)
        self.assertEqual(Notification.objects.filter(is_read=False).count(), 0)