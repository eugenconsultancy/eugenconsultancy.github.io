"""
Tests for revision models.
"""
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta

from apps.revisions.models import RevisionRequest, RevisionCycle
from apps.accounts.models import User
from apps.orders.models import Order


class RevisionModelTests(TestCase):
    """
    Test cases for revision models.
    """
    
    def setUp(self):
        """Set up test data."""
        self.client_user = User.objects.create_user(
            email='client@test.com',
            password='testpass123',
            role=User.Role.CLIENT
        )
        
        self.writer_user = User.objects.create_user(
            email='writer@test.com',
            password='testpass123',
            role=User.Role.WRITER
        )
        
        self.order = Order.objects.create(
            title="Test Order",
            description="Test description",
            amount=100.00,
            deadline=timezone.now() + timedelta(days=7),
            client=self.client_user,
            writer=self.writer_user,
            status='delivered'
        )
    
    def test_create_revision_request(self):
        """Test creating a revision request."""
        revision = RevisionRequest.objects.create(
            order=self.order,
            client=self.client_user,
            writer=self.writer_user,
            title="Test Revision",
            instructions="Please fix formatting",
            deadline=timezone.now() + timedelta(days=3),
            status='requested'
        )
        
        self.assertEqual(revision.title, "Test Revision")
        self.assertEqual(revision.status, 'requested')
        self.assertEqual(revision.revisions_used, 0)
        self.assertEqual(revision.revisions_remaining, 3)  # Default max is 3
    
    def test_revision_state_transitions(self):
        """Test revision state machine transitions."""
        revision = RevisionRequest.objects.create(
            order=self.order,
            client=self.client_user,
            writer=self.writer_user,
            title="Test Revision",
            deadline=timezone.now() + timedelta(days=3),
            status='requested'
        )
        
        # Test start transition
        revision.start_revision(started_by=self.writer_user)
        self.assertEqual(revision.status, 'in_progress')
        self.assertIsNotNone(revision.started_at)
        
        # Test complete transition
        revision.complete_revision(files=[])
        self.assertEqual(revision.status, 'completed')
        self.assertEqual(revision.revisions_used, 1)
        self.assertIsNotNone(revision.completed_at)
    
    def test_revision_cycle_creation(self):
        """Test creating a revision cycle."""
        cycle = RevisionCycle.objects.create(
            order=self.order,
            max_revisions_allowed=3,
            ends_at=timezone.now() + timedelta(days=14)
        )
        
        self.assertEqual(cycle.max_revisions_allowed, 3)
        self.assertEqual(cycle.revisions_used, 0)
        self.assertTrue(cycle.is_active)
        self.assertFalse(cycle.is_expired)
    
    def test_revision_cycle_expiry(self):
        """Test revision cycle expiry."""
        cycle = RevisionCycle.objects.create(
            order=self.order,
            max_revisions_allowed=3,
            ends_at=timezone.now() - timedelta(days=1)  # Already expired
        )
        
        self.assertTrue(cycle.is_expired)
        self.assertFalse(cycle.can_request_revision())
    
    def test_revision_limit(self):
        """Test revision limit enforcement."""
        cycle = RevisionCycle.objects.create(
            order=self.order,
            max_revisions_allowed=2,
            revisions_used=2,
            ends_at=timezone.now() + timedelta(days=14)
        )
        
        self.assertEqual(cycle.revisions_remaining, 0)
        self.assertFalse(cycle.can_request_revision())
    
    def test_invalid_deadline(self):
        """Test validation of deadline in the past."""
        revision = RevisionRequest(
            order=self.order,
            client=self.client_user,
            writer=self.writer_user,
            title="Test Revision",
            deadline=timezone.now() - timedelta(days=1),  # Past deadline
            status='requested'
        )
        
        with self.assertRaises(ValidationError):
            revision.full_clean()
    
    def test_overdue_revision(self):
        """Test overdue revision detection."""
        revision = RevisionRequest.objects.create(
            order=self.order,
            client=self.client_user,
            writer=self.writer_user,
            title="Test Revision",
            deadline=timezone.now() - timedelta(days=1),  # Past deadline
            status='in_progress'
        )
        
        self.assertTrue(revision.is_overdue)
        
        # Check overdue status update
        revision.check_overdue()
        self.assertEqual(revision.status, 'overdue')