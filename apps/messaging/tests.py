# apps/messaging/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
import uuid

from apps.messaging.models import Conversation, Message, MessageAttachment
from apps.orders.models import Order

User = get_user_model()


class MessagingTests(TestCase):
    def setUp(self):
        # Create test users
        self.client_user = User.objects.create_user(
            email='client@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Client'
        )
        
        self.writer_user = User.objects.create_user(
            email='writer@test.com',
            password='testpass123',
            first_name='Writer'
        )
        
        # Create writer profile
        from apps.accounts.models import WriterProfile
        WriterProfile.objects.create(
            user=self.writer_user,
            writer_id='WRITER001',
            specialization='Academic Writing',
            years_experience=3
        )
        
        # Create test order
        self.order = Order.objects.create(
            order_id='#TEST001',
            client=self.client_user,
            title='Test Order',
            description='Test order description',
            total_amount=100.00,
            status='assigned',
            assigned_writer=self.writer_user
        )
        
        # Create conversation
        self.conversation = Conversation.objects.create(order=self.order)
        
        # Create test message
        self.message = Message.objects.create(
            conversation=self.conversation,
            sender=self.client_user,
            content='Test message content'
        )
        
        # Setup API client
        self.api_client = APIClient()
    
    def test_conversation_creation(self):
        """Test conversation is created for order."""
        self.assertEqual(self.order.conversation, self.conversation)
        self.assertFalse(self.conversation.is_closed)
    
    def test_message_creation(self):
        """Test message creation."""
        self.assertEqual(self.message.conversation, self.conversation)
        self.assertEqual(self.message.sender, self.client_user)
        self.assertEqual(self.message.content, 'Test message content')
        self.assertFalse(self.message.is_system_message)
        self.assertFalse(self.message.is_read)
    
    def test_conversation_participants(self):
        """Test conversation participants."""
        participants = self.conversation.participants
        self.assertIn(self.client_user, participants)
        self.assertIn(self.writer_user, participants)
        self.assertEqual(len(participants), 2)
    
    def test_send_message_api(self):
        """Test sending message via API."""
        # Authenticate as client
        self.api_client.force_authenticate(user=self.client_user)
        
        # Send message
        response = self.api_client.post(
            f'/messaging/conversations/{self.conversation.id}/send/',
            {'content': 'New test message'},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check message was created
        self.assertEqual(Message.objects.count(), 2)
        new_message = Message.objects.latest('created_at')
        self.assertEqual(new_message.content, 'New test message')
        self.assertEqual(new_message.sender, self.client_user)
    
    def test_unauthorized_message_access(self):
        """Test unauthorized user cannot access messages."""
        # Create unauthorized user
        unauthorized_user = User.objects.create_user(
            email='unauthorized@test.com',
            password='testpass123'
        )
        
        self.api_client.force_authenticate(user=unauthorized_user)
        
        # Try to get conversation
        response = self.api_client.get(
            f'/messaging/conversations/{self.conversation.id}/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_mark_message_as_read(self):
        """Test marking message as read."""
        # Authenticate as writer (recipient)
        self.api_client.force_authenticate(user=self.writer_user)
        
        # Mark message as read
        response = self.api_client.post(
            f'/messaging/messages/{self.message.id}/read/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh message from database
        self.message.refresh_from_db()
        self.assertTrue(self.message.is_read)
        self.assertIsNotNone(self.message.read_at)
    
    def test_close_conversation_admin_only(self):
        """Test only admin can close conversation."""
        # Try as client (non-admin)
        self.api_client.force_authenticate(user=self.client_user)
        
        response = self.api_client.post(
            f'/messaging/conversations/{self.conversation.id}/close/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Try as admin
        admin_user = User.objects.create_superuser(
            email='admin@test.com',
            password='adminpass123'
        )
        self.api_client.force_authenticate(user=admin_user)
        
        response = self.api_client.post(
            f'/messaging/conversations/{self.conversation.id}/close/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh conversation
        self.conversation.refresh_from_db()
        self.assertTrue(self.conversation.is_closed)


class MessageAttachmentTests(TestCase):
    def setUp(self):
        # Similar setup as above
        self.client_user = User.objects.create_user(
            email='client@test.com',
            password='testpass123'
        )
        
        self.writer_user = User.objects.create_user(
            email='writer@test.com',
            password='testpass123'
        )
        
        self.order = Order.objects.create(
            order_id='#TEST002',
            client=self.client_user,
            title='Test Order',
            total_amount=100.00,
            status='assigned',
            assigned_writer=self.writer_user
        )
        
        self.conversation = Conversation.objects.create(order=self.order)
        self.message = Message.objects.create(
            conversation=self.conversation,
            sender=self.client_user,
            content='Test message with attachment'
        )
    
    def test_attachment_validation(self):
        """Test attachment file validation."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        # Test valid file
        valid_file = SimpleUploadedFile(
            'document.pdf',
            b'Test PDF content',
            content_type='application/pdf'
        )
        
        # Test invalid file type
        invalid_file = SimpleUploadedFile(
            'script.exe',
            b'Malicious content',
            content_type='application/x-msdownload'
        )
        
        # Test oversized file
        oversized_content = b'x' * (11 * 1024 * 1024)  # 11MB
        oversized_file = SimpleUploadedFile(
            'large.pdf',
            oversized_content,
            content_type='application/pdf'
        )
        
        # These would be tested in the service layer
        # For now, we just set up the test structure
        pass