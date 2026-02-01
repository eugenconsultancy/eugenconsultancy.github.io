# apps/disputes/services.py (fix the import)
"""
Services for dispute management.
"""
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
import logging
from django.db import models

from .models import Dispute, DisputeMessage, DisputeResolutionLog
from apps.orders.models.order import Order
from apps.accounts.models import User

logger = logging.getLogger(__name__)

# Fix the import - add apps. prefix
try:
    from apps.payments.services.escrow_service import EscrowService
except ImportError:
    # Create a fallback EscrowService if not available
    class EscrowService:
        @staticmethod
        def freeze_funds(order_id, amount, reason):
            logger.warning(f"EscrowService not available: freeze_funds for order {order_id}")
            return None
        
        @staticmethod
        def release_funds(order_id, recipient_id, amount, reason):
            logger.warning(f"EscrowService not available: release_funds for order {order_id}")
            return None
        
        @staticmethod
        def refund_funds(order_id, sender_id, amount, reason):
            logger.warning(f"EscrowService not available: refund_funds for order {order_id}")
            return None

# Fix the notification import
try:
    from apps.notifications.tasks import deliver_notification as send_notification
except ImportError:
    # Create a fallback function if notifications app is not available
    def send_notification(*args, **kwargs):
        logger.warning(f"Notification sending disabled: {kwargs}")
        return None


class DisputeService:
    """
    Service for managing disputes.
    """
    
    @staticmethod
    @transaction.atomic
    def open_dispute(order_id, user_id, reason, description, evidence_files=None, request=None):
        """
        Open a new dispute.
        
        Args:
            order_id: Order ID
            user_id: User ID opening the dispute
            reason: Dispute reason
            description: Detailed description
            evidence_files: Optional evidence files
            request: HTTP request for audit logging
            
        Returns:
            Dispute instance
        """
        try:
            # Get order
            order = Order.objects.get(id=order_id)
            
            # Check if user has permission to open dispute
            if user_id not in [order.client_id, order.writer_id]:
                raise PermissionDenied("Only order client or writer can open disputes")
            
            # Check if dispute already exists for this order
            if Dispute.objects.filter(order=order, status__in=['open', 'under_review']).exists():
                raise ValidationError("A dispute is already open for this order")
            
            # Determine the other party
            if user_id == order.client_id:
                opened_by = order.client
                against_user = order.writer
            else:
                opened_by = order.writer
                against_user = order.client
            
            # Create dispute
            dispute = Dispute.objects.create(
                order=order,
                opened_by=opened_by,
                against_user=against_user,
                reason=reason,
                initial_description=description,
                status='open'
            )
            
            # Freeze escrow funds if applicable
            try:
                # This assumes order has a total_amount field
                if hasattr(order, 'total_amount') and order.total_amount > 0:
                    EscrowService.freeze_funds(
                        order_id=order.id,
                        amount=order.total_amount,
                        reason=f"Dispute opened: {reason}"
                    )
            except Exception as e:
                logger.warning(f"Failed to freeze escrow funds: {str(e)}")
            
            # Add evidence files if provided
            if evidence_files:
                DisputeService._add_evidence_files(dispute, evidence_files, user_id)
            
            # Create initial message
            DisputeMessage.objects.create(
                dispute=dispute,
                sender=opened_by,
                message=description,
                is_system=False
            )
            
            # Create system message
            DisputeMessage.objects.create(
                dispute=dispute,
                sender=None,  # System
                message=f"Dispute opened by {opened_by.email}. Reason: {reason}",
                is_system=True
            )
            
            # Update order status
            order.status = 'in_dispute'
            order.save()
            
            # Send notifications
            DisputeService._send_dispute_notifications(dispute, 'opened', request)
            
            logger.info(f"Dispute opened: {dispute.id} for order {order_id}")
            return dispute
            
        except Order.DoesNotExist:
            raise ValidationError("Order not found")
        except Exception as e:
            logger.error(f"Error opening dispute: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def add_dispute_message(dispute_id, user_id, message, files=None, request=None):
        """
        Add a message to a dispute.
        
        Args:
            dispute_id: Dispute ID
            user_id: User ID sending the message
            message: Message content
            files: Optional attached files
            request: HTTP request for audit logging
            
        Returns:
            DisputeMessage instance
        """
        try:
            # Get dispute
            dispute = Dispute.objects.get(id=dispute_id)
            
            # Check if user is party to the dispute
            user = User.objects.get(id=user_id)
            if user not in [dispute.opened_by, dispute.against_user] and not user.is_staff:
                raise PermissionDenied("You are not a party to this dispute")
            
            # Check if dispute is open
            if dispute.status not in ['open', 'under_review']:
                raise ValidationError(f"Cannot add messages to dispute in status: {dispute.status}")
            
            # Create message
            dispute_message = DisputeMessage.objects.create(
                dispute=dispute,
                sender=user,
                message=message,
                is_system=False
            )
            
            # Add files if provided
            if files:
                DisputeService._add_evidence_files(dispute, files, user_id)
            
            # Update dispute
            dispute.updated_at = timezone.now()
            dispute.save()
            
            # Send notifications
            DisputeService._send_dispute_notifications(dispute, 'message_added', request, 
                                                     extra_data={'message_id': str(dispute_message.id)})
            
            logger.info(f"Message added to dispute {dispute_id} by user {user_id}")
            return dispute_message
            
        except Dispute.DoesNotExist:
            raise ValidationError("Dispute not found")
        except User.DoesNotExist:
            raise ValidationError("User not found")
        except Exception as e:
            logger.error(f"Error adding dispute message: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def resolve_dispute(dispute_id, resolved_by_id, resolution_type, decision, 
                       amount=None, notes=None, request=None):
        """
        Resolve a dispute.
        
        Args:
            dispute_id: Dispute ID
            resolved_by_id: User ID resolving the dispute
            resolution_type: Type of resolution
            decision: Decision details
            amount: Amount to release/refund (optional)
            notes: Resolution notes (optional)
            request: HTTP request for audit logging
            
        Returns:
            DisputeResolutionLog instance
        """
        try:
            # Get dispute
            dispute = Dispute.objects.get(id=dispute_id)
            
            # Check if user is admin
            resolved_by = User.objects.get(id=resolved_by_id)
            if not resolved_by.is_staff:
                raise PermissionDenied("Only admin users can resolve disputes")
            
            # Check if dispute is open
            if dispute.status not in ['open', 'under_review']:
                raise ValidationError(f"Cannot resolve dispute in status: {dispute.status}")
            
            # Create resolution
            resolution = DisputeResolutionLog.objects.create(
                dispute=dispute,
                resolved_by=resolved_by,
                resolution_type=resolution_type,
                decision=decision,
                notes=notes
            )
            
            # Update dispute status
            dispute.status = 'resolved'
            dispute.resolved_at = timezone.now()
            dispute.save()
            
            # Handle funds based on resolution
            DisputeService._handle_dispute_funds(dispute, resolution_type, decision, amount)
            
            # Update order status
            order = dispute.order
            order.status = 'completed' if resolution_type == 'resolved' else 'cancelled'
            order.save()
            
            # Create system message
            DisputeMessage.objects.create(
                dispute=dispute,
                sender=None,  # System
                message=f"Dispute resolved by {resolved_by.email}. Resolution: {resolution_type}. Decision: {decision}",
                is_system=True
            )
            
            # Send notifications
            DisputeService._send_dispute_notifications(dispute, 'resolved', request,
                                                     extra_data={'resolution_id': str(resolution.id)})
            
            logger.info(f"Dispute resolved: {dispute_id} by user {resolved_by_id}")
            return resolution
            
        except Dispute.DoesNotExist:
            raise ValidationError("Dispute not found")
        except User.DoesNotExist:
            raise ValidationError("User not found")
        except Exception as e:
            logger.error(f"Error resolving dispute: {str(e)}")
            raise
    
    @staticmethod
    def _handle_dispute_funds(dispute, resolution_type, decision, amount=None):
        """
        Handle funds based on dispute resolution.
        
        Args:
            dispute: Dispute instance
            resolution_type: Type of resolution
            decision: Decision details
            amount: Amount to release/refund
        """
        order = dispute.order
        
        if not hasattr(order, 'total_amount') or order.total_amount <= 0:
            return
        
        try:
            if resolution_type == 'client_wins':
                # Release funds to client (refund)
                EscrowService.refund_funds(
                    order_id=order.id,
                    sender_id=dispute.against_user.id,  # Writer
                    amount=amount or order.total_amount,
                    reason=f"Dispute resolved in favor of client: {decision}"
                )
                
            elif resolution_type == 'writer_wins':
                # Release funds to writer
                EscrowService.release_funds(
                    order_id=order.id,
                    recipient_id=dispute.against_user.id,  # Writer
                    amount=amount or order.total_amount,
                    reason=f"Dispute resolved in favor of writer: {decision}"
                )
                
            elif resolution_type == 'partial_settlement':
                # Split funds based on amount
                if amount and amount < order.total_amount:
                    client_amount = order.total_amount - amount
                    writer_amount = amount
                    
                    # Refund to client
                    if client_amount > 0:
                        EscrowService.refund_funds(
                            order_id=order.id,
                            sender_id=dispute.against_user.id,
                            amount=client_amount,
                            reason=f"Partial settlement - client portion: {decision}"
                        )
                    
                    # Release to writer
                    if writer_amount > 0:
                        EscrowService.release_funds(
                            order_id=order.id,
                            recipient_id=dispute.against_user.id,
                            amount=writer_amount,
                            reason=f"Partial settlement - writer portion: {decision}"
                        )
            
        except Exception as e:
            logger.error(f"Error handling dispute funds: {str(e)}")
            raise
    
    @staticmethod
    def _add_evidence_files(dispute, files, user_id):
        """
        Add evidence files to dispute.
        
        Args:
            dispute: Dispute instance
            files: Uploaded files
            user_id: User ID uploading files
        """
        try:
            from apps.documents.models import Document
            
            for file in files.getlist('files', []):
                Document.objects.create(
                    name=file.name,
                    file=file,
                    uploader_id=user_id,
                    document_type='dispute_evidence',
                    related_to='dispute',
                    related_id=dispute.id
                )
            
        except Exception as e:
            logger.error(f"Error adding evidence files: {str(e)}")
    
    @staticmethod
    def _send_dispute_notifications(dispute, action, request=None, extra_data=None):
        """
        Send notifications for dispute actions.
        
        Args:
            dispute: Dispute instance
            action: Action type (opened, message_added, resolved)
            request: HTTP request
            extra_data: Additional data for notifications
        """
        try:
            from apps.notifications.models import Notification
            
            # Define notification templates
            templates = {
                'opened': {
                    'title': 'Dispute Opened',
                    'message': f"A dispute has been opened for Order #{dispute.order.order_number}",
                    'type': 'dispute_opened'
                },
                'message_added': {
                    'title': 'New Dispute Message',
                    'message': f"A new message has been added to dispute for Order #{dispute.order.order_number}",
                    'type': 'dispute_message'
                },
                'resolved': {
                    'title': 'Dispute Resolved',
                    'message': f"The dispute for Order #{dispute.order.order_number} has been resolved",
                    'type': 'dispute_resolved'
                }
            }
            
            template = templates.get(action)
            if not template:
                return
            
            # Notify both parties
            parties = [dispute.opened_by, dispute.against_user]
            
            for party in parties:
                if party:
                    notification = Notification.objects.create(
                        user=party,
                        title=template['title'],
                        message=template['message'],
                        notification_type=template['type'],
                        action_url=f"/disputes/{dispute.id}/"
                    )
                    
                    # Send notification
                    send_notification.delay(str(notification.id))
            
            # Notify admin for opened disputes
            if action == 'opened':
                from django.contrib.auth import get_user_model
                User = get_user_model()
                admin_users = User.objects.filter(is_staff=True, is_active=True)
                
                for admin in admin_users:
                    notification = Notification.objects.create(
                        user=admin,
                        title='New Dispute Requires Attention',
                        message=f"A new dispute has been opened for Order #{dispute.order.order_number}",
                        notification_type='dispute_admin_alert',
                        action_url=f"/admin/disputes/dispute/{dispute.id}/change/"
                    )
                    
                    send_notification.delay(str(notification.id))
            
        except ImportError:
            logger.warning(f"Notifications app not available, skipping dispute notifications")
        except Exception as e:
            logger.error(f"Error sending dispute notifications: {str(e)}")
    
    @staticmethod
    def get_dispute_history(user_id):
        """
        Get dispute history for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            QuerySet of Dispute objects
        """
        try:
            user = User.objects.get(id=user_id)
            
            if user.is_staff:
                # Admin sees all disputes
                return Dispute.objects.all().order_by('-opened_at')
            else:
                # Users see only their disputes
                return Dispute.objects.filter(
                    models.Q(opened_by=user) | models.Q(against_user=user)
                ).order_by('-opened_at')
            
        except User.DoesNotExist:
            raise ValidationError("User not found")
    
    @staticmethod
    def escalate_to_admin(dispute_id, user_id, reason, request=None):
        """
        Escalate a dispute to admin review.
        
        Args:
            dispute_id: Dispute ID
            user_id: User ID requesting escalation
            reason: Escalation reason
            request: HTTP request for audit logging
            
        Returns:
            Dispute instance
        """
        try:
            # Get dispute
            dispute = Dispute.objects.get(id=dispute_id)
            
            # Check if user is party to the dispute
            user = User.objects.get(id=user_id)
            if user not in [dispute.opened_by, dispute.against_user]:
                raise PermissionDenied("You are not a party to this dispute")
            
            # Check if dispute can be escalated
            if dispute.status != 'open':
                raise ValidationError(f"Cannot escalate dispute in status: {dispute.status}")
            
            # Update dispute status
            dispute.status = 'under_review'
            dispute.escalated_at = timezone.now()
            dispute.escalated_by = user
            dispute.escalation_reason = reason
            dispute.save()
            
            # Create system message
            DisputeMessage.objects.create(
                dispute=dispute,
                sender=None,  # System
                message=f"Dispute escalated to admin by {user.email}. Reason: {reason}",
                is_system=True
            )
            
            # Send notifications
            DisputeService._send_dispute_notifications(dispute, 'escalated', request)
            
            logger.info(f"Dispute escalated: {dispute_id} by user {user_id}")
            return dispute
            
        except Dispute.DoesNotExist:
            raise ValidationError("Dispute not found")
        except User.DoesNotExist:
            raise ValidationError("User not found")
        except Exception as e:
            logger.error(f"Error escalating dispute: {str(e)}")
            raise