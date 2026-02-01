"""
Revision management services for controlled revision workflows.
"""
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.conf import settings
import logging
import os
import uuid
from datetime import timedelta

from .models import RevisionRequest, RevisionCycle, RevisionAuditLog
from apps.orders.models.order import Order

logger = logging.getLogger(__name__)

# Import notification function - use deliver_notification instead of send_notification
try:
    from apps.notifications.tasks import deliver_notification as send_notification
except ImportError:
    # Create a fallback function if notifications app is not available
    def send_notification(*args, **kwargs):
        logger.warning(f"Notification sending disabled: {kwargs}")
        return None


class RevisionService:
    """
    Service for managing revision workflows.
    """
    
    @staticmethod
    @transaction.atomic
    def create_revision_request(order_id, client_id, data, files=None, request=None):
        """
        Create a new revision request with validation.
        
        Args:
            order_id: Order ID
            client_id: Client user ID
            data: Dictionary containing revision details
            files: Optional uploaded files
            request: HttpRequest for audit logging
            
        Returns:
            RevisionRequest instance
        """
        try:
            # Get order and validate
            order = Order.objects.get(id=order_id, client_id=client_id)
            
            if order.status not in ['delivered', 'in_revision']:
                raise ValidationError(
                    f"Revisions can only be requested for orders in 'delivered' or 'in_revision' status. Current status: {order.status}"
                )
            
            # Check if revision cycle exists and is active
            try:
                revision_cycle = order.revision_cycle
                if not revision_cycle.can_request_revision():
                    raise ValidationError(
                        "Revision limit reached or revision period has expired"
                    )
            except RevisionCycle.DoesNotExist:
                # Create new revision cycle if needed
                revision_cycle = RevisionCycle.objects.create(
                    order=order,
                    max_revisions_allowed=getattr(settings, 'DEFAULT_MAX_REVISIONS', 3),
                    ends_at=timezone.now() + timedelta(days=14)
                )
            
            # Calculate deadline
            deadline = data.get('deadline')
            if not deadline:
                # Default 7-day deadline from now
                deadline = timezone.now() + timedelta(days=7)
            
            # Create revision request
            revision_request = RevisionRequest.objects.create(
                order=order,
                client_id=client_id,
                writer=order.writer,
                title=data.get('title', f"Revision for Order #{order.order_number}"),
                instructions=data.get('instructions', ''),
                deadline=deadline,
                max_revisions_allowed=revision_cycle.revisions_remaining,
                created_by_id=client_id,
                status='requested'
            )
            
            # Handle files if provided
            if files:
                RevisionService._handle_uploaded_files(
                    files=files,
                    uploader_id=client_id,
                    revision_request=revision_request,
                    document_type='revision_instruction'
                )
            
            # Update order status
            order.status = 'in_revision'
            order.save()
            
            # Update revision cycle
            revision_cycle.revision_requests.add(revision_request)
            
            # Create audit log
            if request:
                RevisionAuditLog.objects.create(
                    revision=revision_request,
                    action='requested',
                    details={
                        'order_id': str(order.id),
                        'client_id': str(client_id),
                        'instructions': data.get('instructions', '')[:100]
                    },
                    performed_by_id=client_id,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            
            # Send notifications - create notification first, then deliver
            if order.writer_id:
                RevisionService._send_notification_to_user(
                    user_id=order.writer_id,
                    title='New Revision Request',
                    message=f"Order #{order.order_number} has a new revision request",
                    notification_type='revision_requested',
                    action_url=f"/orders/{order.id}/revisions/{revision_request.id}/"
                )
            
            logger.info(f"Revision request created: {revision_request.id} for order: {order_id}")
            return revision_request
            
        except Order.DoesNotExist:
            raise ValidationError("Order not found or access denied")
        except Exception as e:
            logger.error(f"Error creating revision request: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def start_revision(revision_id, writer_id, request=None):
        """
        Start working on a revision.
        
        Args:
            revision_id: RevisionRequest ID
            writer_id: Writer user ID
            request: HttpRequest for audit logging
            
        Returns:
            Updated RevisionRequest
        """
        try:
            revision = RevisionRequest.objects.get(id=revision_id, writer_id=writer_id)
            
            # Validate revision can be started
            if revision.status != 'requested':
                raise ValidationError(f"Cannot start revision in status: {revision.status}")
            
            # Start revision
            revision.start_revision()
            
            # Update order status
            order = revision.order
            order.status = 'in_revision'
            order.save()
            
            # Create audit log
            if request:
                RevisionAuditLog.objects.create(
                    revision=revision,
                    action='started',
                    details={'started_by': str(writer_id)},
                    performed_by_id=writer_id,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            
            # Send notification to client
            RevisionService._send_notification_to_user(
                user_id=revision.client_id,
                title='Revision In Progress',
                message=f"Revision for Order #{order.order_number} has been started",
                notification_type='revision_started',
                action_url=f"/orders/{order.id}/revisions/{revision.id}/"
            )
            
            logger.info(f"Revision started: {revision_id} by writer: {writer_id}")
            return revision
            
        except RevisionRequest.DoesNotExist:
            raise ValidationError("Revision not found or access denied")
        except Exception as e:
            logger.error(f"Error starting revision: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def complete_revision(revision_id, writer_id, files, request=None):
        """
        Complete a revision with uploaded files.
        
        Args:
            revision_id: RevisionRequest ID
            writer_id: Writer user ID
            files: Uploaded revised files
            request: HttpRequest for audit logging
            
        Returns:
            Updated RevisionRequest
        """
        try:
            revision = RevisionRequest.objects.get(id=revision_id, writer_id=writer_id)
            
            # Validate revision can be completed
            if revision.status != 'in_progress':
                raise ValidationError(f"Cannot complete revision in status: {revision.status}")
            
            # Upload and validate files
            uploaded_documents = RevisionService._handle_uploaded_files(
                files=files,
                uploader_id=writer_id,
                revision_request=revision,
                document_type='revision_delivery'
            )
            
            # Complete revision
            revision.complete_revision(files=uploaded_documents)
            
            # Add files to revision
            for document in uploaded_documents:
                revision.revised_files.add(document)
            
            # Update revision cycle
            try:
                revision_cycle = revision.order.revision_cycle
                revision_cycle.revisions_used += 1
                revision_cycle.save()
            except RevisionCycle.DoesNotExist:
                # Create revision cycle if it doesn't exist
                revision_cycle = RevisionCycle.objects.create(
                    order=revision.order,
                    max_revisions_allowed=getattr(settings, 'DEFAULT_MAX_REVISIONS', 3),
                    ends_at=timezone.now() + timedelta(days=14),
                    revisions_used=1
                )
            
            # Update order status
            order = revision.order
            order.status = 'delivered'  # Back to delivered for client review
            order.save()
            
            # Create audit log
            if request:
                RevisionAuditLog.objects.create(
                    revision=revision,
                    action='completed',
                    details={
                        'files_count': len(uploaded_documents),
                        'revisions_used': revision.revisions_used
                    },
                    performed_by_id=writer_id,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            
            # Send notification to client
            RevisionService._send_notification_to_user(
                user_id=revision.client_id,
                title='Revision Completed',
                message=f"Revision for Order #{order.order_number} has been completed",
                notification_type='revision_completed',
                action_url=f"/orders/{order.id}/revisions/{revision.id}/"
            )
            
            logger.info(f"Revision completed: {revision_id} with {len(uploaded_documents)} files")
            return revision
            
        except RevisionRequest.DoesNotExist:
            raise ValidationError("Revision not found or access denied")
        except Exception as e:
            logger.error(f"Error completing revision: {str(e)}")
            raise
    
    @staticmethod
    def get_revision_history(order_id, user_id):
        """
        Get revision history for an order.
        
        Args:
            order_id: Order ID
            user_id: User ID for authorization
            
        Returns:
            QuerySet of RevisionRequest objects
        """
        try:
            order = Order.objects.get(id=order_id)
            
            # Check if user has access to this order
            if order.client_id != user_id and order.writer_id != user_id and not order.assigned_admin.filter(id=user_id).exists():
                raise PermissionDenied("Access denied to order revisions")
            
            revisions = RevisionRequest.objects.filter(order=order).order_by('-requested_at')
            return revisions
            
        except Order.DoesNotExist:
            raise ValidationError("Order not found")
    
    @staticmethod
    def check_overdue_revisions():
        """
        Check for overdue revisions and update their status.
        Returns count of overdue revisions.
        """
        overdue_count = 0
        now = timezone.now()
        
        # Find revisions that are overdue
        revisions = RevisionRequest.objects.filter(
            status__in=['requested', 'in_progress'],
            deadline__lt=now
        )
        
        for revision in revisions:
            if revision.check_overdue():
                overdue_count += 1
                
                # Send overdue notification
                if revision.writer_id:
                    RevisionService._send_notification_to_user(
                        user_id=revision.writer_id,
                        title='Revision Overdue',
                        message=f"Revision for Order #{revision.order.order_number} is overdue",
                        notification_type='revision_overdue',
                        action_url=f"/orders/{revision.order.id}/revisions/{revision.id}/"
                    )
                
                logger.warning(f"Revision marked overdue: {revision.id}")
        
        return overdue_count
    
    @staticmethod
    def _handle_uploaded_files(files, uploader_id, revision_request, document_type):
        """
        Handle uploaded files by creating Document records.
        
        Args:
            files: Uploaded files from request.FILES
            uploader_id: ID of user uploading the files
            revision_request: The revision request object
            document_type: Type of document
            
        Returns:
            List of created Document objects
        """
        from apps.documents.models import Document
        
        uploaded_documents = []
        
        for file in files.getlist('files', []):
            # Generate a unique filename
            ext = os.path.splitext(file.name)[1]
            filename = f"{uuid.uuid4()}{ext}"
            
            # Determine upload path
            upload_path = os.path.join('revision_files', str(revision_request.id), filename)
            
            # Create Document record
            document = Document.objects.create(
                name=file.name,
                file=upload_path,
                uploader_id=uploader_id,
                document_type=document_type,
                related_to='revision',
                related_id=revision_request.id
            )
            
            # Save the file
            document.file.save(filename, file, save=True)
            
            uploaded_documents.append(document)
        
        return uploaded_documents
    
    @staticmethod
    def _send_notification_to_user(user_id, title, message, notification_type, action_url=None):
        """
        Send notification to a user.
        
        Args:
            user_id: ID of user to notify
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            action_url: Optional action URL
        """
        try:
            from apps.notifications.models import Notification
            
            notification = Notification.objects.create(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                action_url=action_url
            )
            
            # Deliver the notification
            send_notification.delay(str(notification.id))
            
        except ImportError:
            # Fallback if notifications app is not available
            logger.warning(f"Notifications app not available, skipping notification for user {user_id}")
        except Exception as e:
            logger.error(f"Error sending notification to user {user_id}: {str(e)}")


class RevisionPolicyService:
    """
    Service for managing revision policies and limits.
    """
    
    @staticmethod
    def get_revision_policy(order_type, client_tier='standard'):
        """
        Get revision policy based on order type and client tier.
        
        Args:
            order_type: Type of order (essay, dissertation, etc.)
            client_tier: Client tier (standard, premium, enterprise)
            
        Returns:
            Dictionary with policy details
        """
        policies = {
            'essay': {
                'standard': {'max_revisions': 2, 'deadline_days': 7},
                'premium': {'max_revisions': 3, 'deadline_days': 14},
                'enterprise': {'max_revisions': 5, 'deadline_days': 30},
            },
            'dissertation': {
                'standard': {'max_revisions': 3, 'deadline_days': 14},
                'premium': {'max_revisions': 5, 'deadline_days': 30},
                'enterprise': {'max_revisions': 10, 'deadline_days': 60},
            },
            'default': {
                'standard': {'max_revisions': 2, 'deadline_days': 7},
                'premium': {'max_revisions': 3, 'deadline_days': 14},
                'enterprise': {'max_revisions': 5, 'deadline_days': 30},
            }
        }
        
        return policies.get(order_type, policies['default']).get(
            client_tier, 
            policies['default']['standard']
        )