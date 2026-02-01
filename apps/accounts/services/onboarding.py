from typing import Dict, Optional, TYPE_CHECKING
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from apps.accounts.models import WriterProfile, WriterVerificationStatus
from apps.compliance.models import ConsentLog

# Import the model only for type hinting to avoid circular imports and variable-type errors
if TYPE_CHECKING:
    from apps.accounts.models import User as UserType

User = get_user_model()

class OnboardingService:
    """Service for managing writer onboarding workflow."""
    
    @classmethod
    @transaction.atomic
    def register_writer(cls, email: str, password: str, **extra_fields) -> "UserType":
        """
        Register a new writer with proper state initialization.
        
        Args:
            email: Writer's email address
            password: Writer's password
            **extra_fields: Additional user fields (e.g., registration_ip, user_agent)
            
        Returns:
            Created User object
        """
        # Extract fields meant for ConsentLog so they don't break create_user
        reg_ip = extra_fields.pop('registration_ip', None)
        u_agent = extra_fields.pop('user_agent', None)

        # Create user with writer type
        user = User.objects.create_user(
            email=email,
            password=password,
            user_type=User.UserType.WRITER,
            **extra_fields
        )
        
        # Create writer profile
        WriterProfile.objects.create(user=user)
        
        # Create verification status with initial state
        WriterVerificationStatus.objects.create(
            user=user,
            state='registered'
        )
        
        # Log consent
        ConsentLog.objects.create(
            user=user,
            action='registration',
            ip_address=reg_ip,
            user_agent=u_agent,
        )
        
        return user
    
    @classmethod
    @transaction.atomic
    def complete_writer_profile(cls, user_id: int, profile_data: Dict) -> WriterProfile:
        """
        Complete writer profile and transition to next state.
        
        Args:
            user_id: ID of the user
            profile_data: Dictionary containing profile information
            
        Returns:
            Updated WriterProfile object
        
        Raises:
            ValidationError: If profile data is invalid
            PermissionError: If user cannot complete profile
        """
        user = User.objects.get(id=user_id)
        
        if not user.is_writer:
            raise ValidationError("User is not a writer.")
        
        verification_status = user.verification_status
        
        # Check if user can complete profile
        if verification_status.state != 'registered':
            raise ValidationError(
                f"Cannot complete profile from state: {verification_status.state}"
            )
        
        # Update writer profile
        writer_profile = user.writer_profile
        
        # Update profile fields
        for field, value in profile_data.items():
            if hasattr(writer_profile, field):
                setattr(writer_profile, field, value)
        
        writer_profile.status = WriterProfile.Status.ACTIVE
        writer_profile.profile_completed_at = timezone.now()
        writer_profile.save()
        
        # Transition verification state
        verification_status.complete_profile()
        verification_status.save()
        
        return writer_profile
    
    @classmethod
    def get_onboarding_status(cls, user_id: int) -> Dict:
        """
        Get current onboarding status for a writer.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dictionary with onboarding status information
        """
        user = User.objects.get(id=user_id)
        
        if not hasattr(user, 'verification_status'):
            return {'error': 'User is not a writer'}
        
        verification = user.verification_status
        
        # Get document status
        documents = user.documents.all()
        document_summary = {
            'total': documents.count(),
            'verified': documents.filter(status='verified').count(),
            'pending': documents.filter(status='pending').count(),
            'rejected': documents.filter(status='rejected').count(),
        }
        
        # Check if profile is complete
        profile_complete = bool(user.writer_profile.profile_completed_at)
        
        return {
            'current_state': verification.state,
            'current_state_display': verification.get_state_display(),
            'profile_complete': profile_complete,
            'documents': document_summary,
            'next_action': cls._get_next_action(verification.state),
            'can_proceed': cls._can_proceed_to_next_step(verification, document_summary),
            'created_at': verification.created_at,
            'updated_at': verification.updated_at,
        }
    
    @classmethod
    def _get_next_action(cls, state: str) -> str:
        """Determine next action based on current state."""
        actions = {
            'registered': 'Complete your profile',
            'profile_completed': 'Submit verification documents',
            'documents_submitted': 'Wait for admin review',
            'under_admin_review': 'Wait for admin decision',
            'approved': 'Start accepting orders',
            'rejected': 'Review rejection reason and resubmit',
            'revision_required': 'Review revision notes and update documents',
        }
        return actions.get(state, 'Unknown state')
    
    @classmethod
    def _can_proceed_to_next_step(cls, verification, document_summary) -> bool:
        """Check if user can proceed to next onboarding step."""
        if verification.state == 'registered':
            return True  # Always can start profile
        
        if verification.state == 'profile_completed':
            # Need at least 3 documents for submission
            return document_summary['verified'] >= 3
        
        if verification.state in ['rejected', 'revision_required']:
            return True  # Can always resubmit
        
        return False
    
    @classmethod
    def get_writer_stats(cls) -> Dict:
        """Get platform-wide writer statistics."""
        total_writers = User.objects.filter(user_type=User.UserType.WRITER).count()
        
        verification_stats = {}
        for state_code, state_name in WriterVerificationStatus.STATE_CHOICES:
            count = WriterVerificationStatus.objects.filter(state=state_code).count()
            verification_stats[state_code] = {
                'count': count,
                'percentage': (count / total_writers * 100) if total_writers > 0 else 0,
                'name': state_name,
            }
        
        return {
            'total_writers': total_writers,
            'verification_stats': verification_stats,
            'average_review_time': cls._calculate_average_review_time(),
        }
    
    @classmethod
    def _calculate_average_review_time(cls) -> Optional[int]:
        """Calculate average time spent in admin review."""
        from django.db.models import Avg, F
        
        completed_reviews = WriterVerificationStatus.objects.filter(
            state__in=['approved', 'rejected'],
            review_started_at__isnull=False,
            review_completed_at__isnull=False,
        )
        
        if not completed_reviews.exists():
            return None
        
        # Calculate average in seconds
        avg_seconds = completed_reviews.annotate(
            review_time=F('review_completed_at') - F('review_started_at')
        ).aggregate(
            avg_seconds=Avg('review_time')
        )['avg_seconds']
        
        if avg_seconds:
            return avg_seconds.total_seconds() / 3600  # Convert to hours
        
        return None