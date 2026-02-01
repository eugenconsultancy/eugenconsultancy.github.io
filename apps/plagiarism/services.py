# apps/plagiarism/services.py (fix the import)
"""
Services for plagiarism detection.
"""
import logging
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import PlagiarismCheck, PlagiarismReport, PlagiarismPolicy
from .api_clients import PlagiarismClientFactory
from apps.orders.models.order import Order

logger = logging.getLogger(__name__)

# Fix the import - change send_notification to deliver_notification
try:
    from apps.notifications.tasks import deliver_notification as send_notification
except ImportError:
    # Create a fallback function if notifications app is not available
    def send_notification(*args, **kwargs):
        logger.warning(f"Notification sending disabled: {kwargs}")
        return None


class PlagiarismService:
    """
    Service for managing plagiarism checks.
    """
    
    @staticmethod
    @transaction.atomic
    def request_plagiarism_check(order_id, user_id, source='internal', file_id=None):
        """
        Request a plagiarism check for an order.
        
        Args:
            order_id: Order ID
            user_id: User ID requesting the check
            source: Plagiarism check source
            file_id: Specific file ID to check (optional)
            
        Returns:
            PlagiarismCheck instance
        """
        try:
            # Get order
            order = Order.objects.get(id=order_id)
            
            # Check if user has permission
            if not user_id in [order.client_id, order.writer_id] and not order.assigned_admin.filter(id=user_id).exists():
                raise ValidationError("You don't have permission to request plagiarism checks for this order")
            
            # Get file to check
            from apps.documents.models import Document
            
            if file_id:
                file_to_check = Document.objects.get(id=file_id, related_to='order', related_id=order_id)
            else:
                # Get the most recent delivery file
                file_to_check = Document.objects.filter(
                    related_to='order',
                    related_id=order_id,
                    document_type='delivery'
                ).order_by('-created_at').first()
                
                if not file_to_check:
                    raise ValidationError("No delivery files found for plagiarism check")
            
            # Create plagiarism check request
            plagiarism_check = PlagiarismCheck.objects.create(
                order=order,
                source=source,
                checked_file=file_to_check,
                requested_by_id=user_id,
                status='requested'
            )
            
            # Log the request
            logger.info(f"Plagiarism check requested for order {order_id} by user {user_id}")
            
            return plagiarism_check
            
        except Order.DoesNotExist:
            raise ValidationError("Order not found")
        except Document.DoesNotExist:
            raise ValidationError("File not found")
        except Exception as e:
            logger.error(f"Error requesting plagiarism check: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def process_plagiarism_check(check_id, processed_by_id):
        """
        Process a plagiarism check.
        
        Args:
            check_id: Plagiarism check ID
            processed_by_id: User ID processing the check
            
        Returns:
            PlagiarismCheck instance
        """
        try:
            # Get the check
            check = PlagiarismCheck.objects.get(id=check_id)
            
            # Check if already processed
            if check.status != 'requested':
                raise ValidationError(f"Cannot process check in status: {check.status}")
            
            # Update status
            check.status = 'processing'
            check.started_at = timezone.now()
            check.processed_by_id = processed_by_id
            check.save()
            
            try:
                # Get the appropriate client
                client = PlagiarismClientFactory.get_client(check.source)
                
                # Process the check
                result = client.check_plagiarism(check.checked_file)
                
                # Update with results
                check.status = 'completed'
                check.completed_at = timezone.now()
                check.similarity_score = result.get('similarity_score', 0)
                check.word_count = result.get('word_count', 0)
                check.character_count = result.get('character_count', 0)
                check.raw_result = result.get('raw_result', {})
                check.highlights = result.get('highlights', {})
                check.sources = result.get('sources', [])
                check.risk_level = PlagiarismService._calculate_risk_level(
                    check.similarity_score,
                    check.order.order_type if hasattr(check.order, 'order_type') else 'essay'
                )
                
                # Check against policies
                policy_violation = PlagiarismService._check_policy_violation(check)
                if policy_violation:
                    check.is_sensitive = True
                    check.policy_violation = policy_violation
                    
                    # Send notification if policy violation
                    PlagiarismService._send_policy_violation_notification(check)
                
                check.save()
                
                # Generate report
                PlagiarismService._generate_report(check)
                
                logger.info(f"Plagiarism check completed: {check_id} with score {check.similarity_score}%")
                
            except Exception as e:
                # Mark as failed
                check.status = 'failed'
                check.completed_at = timezone.now()
                check.error_message = str(e)
                check.save()
                logger.error(f"Error processing plagiarism check {check_id}: {str(e)}")
                raise
            
            return check
            
        except PlagiarismCheck.DoesNotExist:
            raise ValidationError("Plagiarism check not found")
        except Exception as e:
            logger.error(f"Error processing plagiarism check: {str(e)}")
            raise
    
    @staticmethod
    def _calculate_risk_level(similarity_score, order_type='essay'):
        """
        Calculate risk level based on similarity score and order type.
        
        Args:
            similarity_score: Similarity percentage
            order_type: Type of order
            
        Returns:
            Risk level string
        """
        # Define thresholds based on order type
        thresholds = {
            'essay': {'low': 10, 'medium': 25, 'high': 50},
            'dissertation': {'low': 5, 'medium': 15, 'high': 30},
            'thesis': {'low': 5, 'medium': 15, 'high': 30},
            'default': {'low': 10, 'medium': 25, 'high': 50}
        }
        
        thresholds_config = thresholds.get(order_type, thresholds['default'])
        
        if similarity_score < thresholds_config['low']:
            return 'low'
        elif similarity_score < thresholds_config['medium']:
            return 'medium'
        elif similarity_score < thresholds_config['high']:
            return 'high'
        else:
            return 'critical'
    
    @staticmethod
    def _check_policy_violation(check):
        """
        Check if plagiarism check violates any policies.
        
        Args:
            check: PlagiarismCheck instance
            
        Returns:
            Policy violation message or None
        """
        try:
            # Get applicable policies
            policies = PlagiarismPolicy.objects.filter(
                is_active=True,
                order_types__contains=[check.order.order_type] if hasattr(check.order, 'order_type') else []
            )
            
            for policy in policies:
                if check.similarity_score >= policy.rejection_threshold:
                    return {
                        'policy': policy.name,
                        'threshold': policy.rejection_threshold,
                        'score': check.similarity_score,
                        'action': policy.critical_action,
                        'level': 'critical'
                    }
                elif check.similarity_score >= policy.action_threshold:
                    return {
                        'policy': policy.name,
                        'threshold': policy.action_threshold,
                        'score': check.similarity_score,
                        'action': policy.critical_action,
                        'level': 'action'
                    }
                elif check.similarity_score >= policy.warning_threshold:
                    return {
                        'policy': policy.name,
                        'threshold': policy.warning_threshold,
                        'score': check.similarity_score,
                        'action': policy.warning_action,
                        'level': 'warning'
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking policy violation: {str(e)}")
            return None
    
    @staticmethod
    def _send_policy_violation_notification(check):
        """
        Send notification for policy violation.
        
        Args:
            check: PlagiarismCheck instance
        """
        try:
            from apps.notifications.models import Notification
            
            # Notify admin
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_users = User.objects.filter(is_staff=True, is_active=True)
            
            for admin in admin_users:
                notification = Notification.objects.create(
                    user=admin,
                    title='Plagiarism Policy Violation',
                    message=f"Order #{check.order.order_number} has {check.similarity_score}% plagiarism ({check.risk_level} risk)",
                    notification_type='plagiarism_violation',
                    action_url=f"/admin/plagiarism/plagiarismcheck/{check.id}/change/"
                )
                
                # Send notification
                send_notification.delay(str(notification.id))
            
            logger.info(f"Policy violation notifications sent for check {check.id}")
            
        except ImportError:
            logger.warning(f"Notifications app not available, skipping policy violation notification")
        except Exception as e:
            logger.error(f"Error sending policy violation notification: {str(e)}")
    
    @staticmethod
    def _generate_report(check):
        """
        Generate a plagiarism report.
        
        Args:
            check: PlagiarismCheck instance
        """
        try:
            # Check if report already exists
            if hasattr(check, 'report'):
                return check.report
            
            # Generate access key
            import secrets
            access_key = secrets.token_urlsafe(32)
            
            # Create report
            report = PlagiarismReport.objects.create(
                plagiarism_check=check,
                title=f"Plagiarism Report for Order #{check.order.order_number}",
                summary=f"Similarity score: {check.similarity_score}% - Risk level: {check.risk_level}",
                access_key=access_key,
                is_encrypted=check.is_sensitive,
                expires_at=timezone.now() + timezone.timedelta(days=30)
            )
            
            # Add detailed analysis if not sensitive
            if not check.is_sensitive:
                report.detailed_analysis = {
                    'similarity_score': check.similarity_score,
                    'word_count': check.word_count,
                    'character_count': check.character_count,
                    'risk_level': check.risk_level,
                    'highlights': check.highlights,
                    'sources': check.sources[:10],  # Limit to top 10 sources
                    'generated_at': timezone.now().isoformat()
                }
                report.save()
            
            logger.info(f"Plagiarism report generated: {report.id}")
            return report
            
        except Exception as e:
            logger.error(f"Error generating plagiarism report: {str(e)}")
            return None
    
    @staticmethod
    def get_report_by_access_key(access_key):
        """
        Get plagiarism report by access key.
        
        Args:
            access_key: Report access key
            
        Returns:
            PlagiarismReport instance
        """
        try:
            report = PlagiarismReport.objects.get(
                access_key=access_key,
                expires_at__gt=timezone.now()
            )
            
            # Increment view count
            report.view_count += 1
            report.last_viewed = timezone.now()
            report.save()
            
            return report
            
        except PlagiarismReport.DoesNotExist:
            return None
    
    @staticmethod
    def cleanup_expired_reports(days=90):
        """
        Clean up expired plagiarism reports.
        
        Args:
            days: Number of days to keep reports
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        try:
            # Delete expired reports
            expired_reports = PlagiarismReport.objects.filter(expires_at__lt=cutoff_date)
            count = expired_reports.count()
            expired_reports.delete()
            
            logger.info(f"Cleaned up {count} expired plagiarism reports")
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired reports: {str(e)}")
            return 0