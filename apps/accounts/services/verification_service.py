from typing import Dict, Optional
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings

from apps.accounts.models import WriterVerificationStatus
from apps.notifications.tasks import send_verification_notification


class VerificationService:
    """Service for managing writer verification workflow."""
    
    @classmethod
    @transaction.atomic
    def submit_for_verification(cls, user) -> WriterVerificationStatus:
        """
        Submit writer for admin verification.
        
        Args:
            user: User to submit for verification
            
        Returns:
            Updated WriterVerificationStatus object
        
        Raises:
            ValidationError: If cannot submit for verification
        """
        verification = user.verification_status
        
        # Check if user can submit documents
        if verification.state != 'profile_completed':
            raise ValidationError(
                f"Cannot submit documents from state: {verification.state}"
            )
        
        # Check minimum document requirements
        verified_docs = user.documents.filter(status='verified').count()
        if verified_docs < 3:
            raise ValidationError(
                f"Need at least 3 verified documents. Currently have: {verified_docs}"
            )
        
        # Transition state
        verification.submit_documents()
        verification.save()
        
        # Notify admins
        cls._notify_admins_of_submission(user)
        
        return verification
    
    @classmethod
    @transaction.atomic
    def start_admin_review(
        cls,
        verification_id: int,
        admin_user
    ) -> WriterVerificationStatus:
        """
        Start admin review of a verification submission.
        
        Args:
            verification_id: ID of the verification to review
            admin_user: Admin user starting the review
            
        Returns:
            Updated WriterVerificationStatus object
        """
        if not admin_user.is_staff:
            raise PermissionError("Only staff can start admin review.")
        
        verification = WriterVerificationStatus.objects.get(id=verification_id)
        
        # Check if can start review
        if verification.state != 'documents_submitted':
            raise ValidationError(
                f"Cannot start review from state: {verification.state}"
            )
        
        # Transition state
        verification.start_admin_review(admin_user)
        verification.save()
        
        # Notify writer
        send_verification_notification.delay(
            user_id=verification.user.id,
            notification_type='review_started',
            admin_name=admin_user.get_full_name(),
        )
        
        return verification
    
    @classmethod
    @transaction.atomic
    def approve_writer(
        cls,
        verification_id: int,
        admin_user,
        notes: str = ''
    ) -> WriterVerificationStatus:
        """
        Approve a writer (admin action).
        
        Args:
            verification_id: ID of the verification to approve
            admin_user: Admin user approving
            notes: Approval notes
            
        Returns:
            Updated WriterVerificationStatus object
        """
        if not admin_user.is_staff:
            raise PermissionError("Only staff can approve writers.")
        
        verification = WriterVerificationStatus.objects.get(id=verification_id)
        
        # Check if can approve
        if verification.state != 'under_admin_review':
            raise ValidationError(
                f"Cannot approve from state: {verification.state}"
            )
        
        # Transition state
        verification.approve(admin_user)
        verification.save()
        
        # Notify writer
        send_verification_notification.delay(
            user_id=verification.user.id,
            notification_type='approved',
            admin_name=admin_user.get_full_name(),
            notes=notes,
        )
        
        return verification
    
    @classmethod
    @transaction.atomic
    def reject_writer(
        cls,
        verification_id: int,
        admin_user,
        reason: str
    ) -> WriterVerificationStatus:
        """
        Reject a writer (admin action).
        
        Args:
            verification_id: ID of the verification to reject
            admin_user: Admin user rejecting
            reason: Reason for rejection
            
        Returns:
            Updated WriterVerificationStatus object
        """
        if not admin_user.is_staff:
            raise PermissionError("Only staff can reject writers.")
        
        verification = WriterVerificationStatus.objects.get(id=verification_id)
        
        # Check if can reject
        if verification.state != 'under_admin_review':
            raise ValidationError(
                f"Cannot reject from state: {verification.state}"
            )
        
        # Transition state
        verification.reject(admin_user, reason)
        verification.save()
        
        # Notify writer
        send_verification_notification.delay(
            user_id=verification.user.id,
            notification_type='rejected',
            admin_name=admin_user.get_full_name(),
            reason=reason,
        )
        
        return verification
    
    @classmethod
    @transaction.atomic
    def require_revision(
        cls,
        verification_id: int,
        admin_user,
        notes: str
    ) -> WriterVerificationStatus:
        """
        Request revision from writer (admin action).
        
        Args:
            verification_id: ID of the verification requiring revision
            admin_user: Admin user requesting revision
            notes: Revision notes
            
        Returns:
            Updated WriterVerificationStatus object
        """
        if not admin_user.is_staff:
            raise PermissionError("Only staff can request revisions.")
        
        verification = WriterVerificationStatus.objects.get(id=verification_id)
        
        # Check if can request revision
        if verification.state != 'under_admin_review':
            raise ValidationError(
                f"Cannot request revision from state: {verification.state}"
            )
        
        # Transition state
        verification.require_revision(admin_user, notes)
        verification.save()
        
        # Notify writer
        send_verification_notification.delay(
            user_id=verification.user.id,
            notification_type='revision_required',
            admin_name=admin_user.get_full_name(),
            notes=notes,
        )
        
        return verification
    
    @classmethod
    def _notify_admins_of_submission(cls, user):
        """Notify admins of new verification submission."""
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        admins = User.objects.filter(
            is_staff=True,
            is_active=True
        )
        
        for admin in admins:
            send_verification_notification.delay(
                user_id=admin.id,
                notification_type='new_submission',
                writer_email=user.email,
                writer_name=user.get_full_name(),
            )
    
    @classmethod
    def get_verification_queue(cls) -> Dict:
        """
        Get verification queue for admin dashboard.
        
        Returns:
            Dictionary with verification queue data
        """
        queue = {
            'pending_submission': [],
            'in_review': [],
            'recently_processed': [],
        }
        
        # Writers waiting for admin to start review
        pending = WriterVerificationStatus.objects.filter(
            state='documents_submitted'
        ).select_related('user', 'user__writer_profile')
        
        for verification in pending:
            queue['pending_submission'].append({
                'id': verification.id,
                'user_id': verification.user.id,
                'email': verification.user.email,
                'name': verification.user.get_full_name(),
                'submitted_at': verification.documents_submitted_at,
                'documents_count': verification.user.documents.filter(status='verified').count(),
                'profile_completed_at': verification.profile_completed_at,
            })
        
        # Writers currently under review
        in_review = WriterVerificationStatus.objects.filter(
            state='under_admin_review'
        ).select_related('user', 'user__writer_profile')
        
        for verification in in_review:
            queue['in_review'].append({
                'id': verification.id,
                'user_id': verification.user.id,
                'email': verification.user.email,
                'name': verification.user.get_full_name(),
                'review_started_at': verification.review_started_at,
                'time_in_review': verification.time_in_review,
                'reviewed_by': verification.reviewed_by.get_full_name() if verification.reviewed_by else None,
            })
        
        # Recently processed verifications (last 7 days)
        seven_days_ago = timezone.now() - timezone.timedelta(days=7)
        recent = WriterVerificationStatus.objects.filter(
            state__in=['approved', 'rejected'],
            review_completed_at__gte=seven_days_ago
        ).select_related('user', 'approved_by', 'rejected_by')
        
        for verification in recent:
            queue['recently_processed'].append({
                'id': verification.id,
                'user_id': verification.user.id,
                'email': verification.user.email,
                'name': verification.user.get_full_name(),
                'final_state': verification.get_state_display(),
                'processed_at': verification.review_completed_at,
                'processed_by': (
                    verification.approved_by.get_full_name() 
                    if verification.approved_by 
                    else verification.rejected_by.get_full_name()
                ),
                'reason': verification.rejection_reason or verification.revision_notes or '',
            })
        
        return queue
    
    @classmethod
    def get_verification_metrics(cls) -> Dict:
        """Get verification process metrics."""
        from django.db.models import Count, Avg, F
        
        metrics = {}
        
        # Total counts by state
        state_counts = WriterVerificationStatus.objects.values('state').annotate(
            count=Count('id')
        )
        
        metrics['state_distribution'] = {
            item['state']: item['count'] 
            for item in state_counts
        }
        
        # Average review time
        completed = WriterVerificationStatus.objects.filter(
            state__in=['approved', 'rejected'],
            review_started_at__isnull=False,
            review_completed_at__isnull=False,
        )
        
        if completed.exists():
            avg_review_time = completed.annotate(
                duration=F('review_completed_at') - F('review_started_at')
            ).aggregate(
                avg_duration=Avg('duration')
            )['avg_duration']
            
            if avg_review_time:
                metrics['avg_review_hours'] = avg_review_time.total_seconds() / 3600
        
        # Approval rate
        total_processed = WriterVerificationStatus.objects.filter(
            state__in=['approved', 'rejected']
        ).count()
        
        approved_count = WriterVerificationStatus.objects.filter(
            state='approved'
        ).count()
        
        if total_processed > 0:
            metrics['approval_rate'] = (approved_count / total_processed) * 100
        
        # Monthly trend (last 6 months)
        from django.db.models.functions import TruncMonth
        
        six_months_ago = timezone.now() - timezone.timedelta(days=180)
        
        monthly_trend = WriterVerificationStatus.objects.filter(
            created_at__gte=six_months_ago
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month', 'state').annotate(
            count=Count('id')
        ).order_by('month')
        
        metrics['monthly_trend'] = list(monthly_trend)
        
        return metrics