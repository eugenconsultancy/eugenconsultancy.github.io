from typing import Dict, Optional
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings

from apps.orders.models import Order
from apps.payments.services.escrow_service import EscrowService
from apps.notifications.tasks import send_order_notification


class DisputeService:
    """Service for handling order disputes."""
    
    @classmethod
    @transaction.atomic
    def raise_dispute(
        cls,
        order_id: int,
        client_id: int,
        reason: str,
        details: str = '',
        evidence_files: Optional[list] = None
    ) -> Order:
        """
        Raise a dispute for an order.
        
        Args:
            order_id: ID of the order
            client_id: ID of the client raising dispute
            reason: Reason for dispute
            details: Detailed explanation
            evidence_files: Optional evidence files
            
        Returns:
            Updated Order object
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            order = Order.objects.select_for_update().get(id=order_id)
            client = User.objects.get(id=client_id)
            
            # Validate permissions
            if order.client != client:
                raise ValidationError("You are not the client for this order.")
            
            # Check if dispute can be raised
            valid_states = ['delivered', 'in_revision', 'revision_requested']
            if order.state not in valid_states:
                raise ValidationError(
                    f"Cannot raise dispute for order in state: {order.state}"
                )
            
            # Check if dispute is already raised
            if order.state == 'disputed':
                raise ValidationError("Dispute already raised for this order.")
            
            # Check time limit (7 days from delivery for disputes)
            if order.delivered_at:
                dispute_deadline = order.delivered_at + timezone.timedelta(days=7)
                if timezone.now() > dispute_deadline:
                    raise ValidationError(
                        "Dispute period has expired (7 days from delivery)."
                    )
            
            # Raise dispute
            order.dispute(reason)
            order.save()
            
            # Save evidence files if provided
            if evidence_files:
                cls._save_evidence_files(order, client, evidence_files)
            
            # Log dispute
            cls._log_dispute(order, client, reason, details)
            
            # Send notifications
            cls._send_dispute_notifications(order, client, reason)
            
            return order
            
        except (Order.DoesNotExist, User.DoesNotExist) as e:
            raise ValidationError(f"Invalid order or client: {str(e)}")
    
    @classmethod
    def _save_evidence_files(cls, order, client, files):
        """Save dispute evidence files."""
        from apps.accounts.services.document_validator import DocumentValidator
        from apps.orders.models import OrderFile
        
        for file_obj in files:
            try:
                validation_result = DocumentValidator.validate_file(file_obj)
            except ValidationError as e:
                raise ValidationError(f"Evidence file validation failed: {str(e)}")
            
            # Create order file record for evidence
            order_file = OrderFile(
                order=order,
                uploaded_by=client,
                file_type='other',
                description=f'Dispute evidence - {order.dispute_reason}',
                original_filename=validation_result['original_filename'],
                file_size=validation_result['file_size'],
                mime_type=validation_result['mime_type'],
                file_hash=validation_result['file_hash'],
            )
            
            order_file.file.save(file_obj.name, file_obj, save=False)
            order_file.save()
    
    @classmethod
    def _log_dispute(cls, order, client, reason: str, details: str):
        """Log dispute for audit trail."""
        from apps.compliance.models import AuditLog
        
        AuditLog.objects.create(
            user=client,
            action_type='update',
            model_name='Order',
            object_id=str(order.id),
            changes={
                'state': {'old': order._state_before, 'new': 'disputed'},
                'dispute_reason': reason,
                'dispute_details': details,
                'raised_at': timezone.now().isoformat(),
            },
            before_state={'state': order._state_before, 'dispute_reason': ''},
            after_state={'state': 'disputed', 'dispute_reason': reason},
        )
    
    @classmethod
    def _send_dispute_notifications(cls, order, client, reason: str):
        """Send notifications about dispute."""
        # Notify writer
        send_order_notification.delay(
            user_id=order.writer.id,
            order_id=order.id,
            notification_type='dispute_raised',
            client_name=client.get_full_name(),
            reason=reason,
        )
        
        # Notify admins
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        admins = User.objects.filter(
            is_staff=True,
            is_active=True
        )
        
        for admin in admins:
            send_order_notification.delay(
                user_id=admin.id,
                order_id=order.id,
                notification_type='admin_dispute_raised',
                client_name=client.get_full_name(),
                writer_name=order.writer.get_full_name(),
                reason=reason,
                order_price=str(order.price),
            )
    
    @classmethod
    @transaction.atomic
    def resolve_dispute(
        cls,
        order_id: int,
        admin_user,
        resolution_type: str,
        refund_amount: Optional[float] = None,
        notes: str = ''
    ) -> Order:
        """
        Resolve a dispute (admin action).
        
        Args:
            order_id: ID of the order
            admin_user: Admin user resolving dispute
            resolution_type: Type of resolution
            refund_amount: Refund amount (if applicable)
            notes: Resolution notes
            
        Returns:
            Updated Order object
        """
        if not admin_user.is_staff:
            raise PermissionError("Only staff can resolve disputes.")
        
        try:
            order = Order.objects.select_for_update().get(id=order_id)
            
            # Check if order is in dispute
            if order.state != 'disputed':
                raise ValidationError(f"Order is not in disputed state: {order.state}")
            
            # Process resolution based on type
            if resolution_type == 'full_refund':
                cls._process_full_refund(order, admin_user, notes)
                
            elif resolution_type == 'partial_refund':
                if not refund_amount:
                    raise ValidationError("Refund amount required for partial refund.")
                cls._process_partial_refund(order, admin_user, refund_amount, notes)
                
            elif resolution_type == 'writer_payment':
                cls._process_writer_payment(order, admin_user, notes)
                
            elif resolution_type == 'split_payment':
                if not refund_amount:
                    # Default to 50% refund
                    refund_amount = order.price * 0.5
                cls._process_split_payment(order, admin_user, refund_amount, notes)
                
            elif resolution_type == 'reopen_order':
                cls._reopen_order(order, admin_user, notes)
                
            elif resolution_type == 'no_action':
                cls._reject_dispute(order, admin_user, notes)
                
            else:
                raise ValidationError(f"Invalid resolution type: {resolution_type}")
            
            # Log resolution
            cls._log_resolution(order, admin_user, resolution_type, refund_amount, notes)
            
            # Send notifications
            cls._send_resolution_notifications(order, admin_user, resolution_type, notes)
            
            return order
            
        except Order.DoesNotExist as e:
            raise ValidationError(f"Order not found: {str(e)}")
    
    @classmethod
    def _process_full_refund(cls, order, admin_user, notes: str):
        """Process full refund to client."""
        # Refund full amount
        EscrowService.refund_order(order.id, order.price)
        
        # Update order state
        order.refund(order.price, admin_user)
        order.save()
    
    @classmethod
    def _process_partial_refund(cls, order, admin_user, refund_amount: float, notes: str):
        """Process partial refund to client."""
        if refund_amount > order.price:
            raise ValidationError("Refund amount cannot exceed order price.")
        
        # Refund partial amount
        EscrowService.refund_order(order.id, refund_amount)
        
        # Pay writer the remainder (if any)
        writer_amount = order.price - refund_amount
        if writer_amount > 0:
            # Release to writer's wallet
            if hasattr(order, 'payment'):
                order.payment.writer_amount = writer_amount
                order.payment.save()
        
        # Update order state
        order.refund(refund_amount, admin_user)
        order.save()
    
    @classmethod
    def _process_writer_payment(cls, order, admin_user, notes: str):
        """Process payment to writer (dispute rejected)."""
        # Release full payment to writer
        if hasattr(order, 'payment'):
            from apps.payments.services.escrow_service import EscrowService
            EscrowService.release_escrow_funds(order.payment.id, admin_user)
        
        # Update order state to completed
        order.state = 'completed'
        order.completed_at = timezone.now()
        order.save()
    
    @classmethod
    def _process_split_payment(cls, order, admin_user, refund_amount: float, notes: str):
        """Process split payment (partial refund, partial to writer)."""
        if refund_amount > order.price:
            raise ValidationError("Refund amount cannot exceed order price.")
        
        writer_amount = order.price - refund_amount
        
        # Process refund
        if refund_amount > 0:
            EscrowService.refund_order(order.id, refund_amount)
        
        # Process writer payment
        if writer_amount > 0 and hasattr(order, 'payment'):
            order.payment.writer_amount = writer_amount
            order.payment.save()
            from apps.payments.services.escrow_service import EscrowService
            EscrowService.release_escrow_funds(order.payment.id, admin_user)
        
        # Update order state
        order.refund(refund_amount, admin_user)
        order.state = 'completed'
        order.completed_at = timezone.now()
        order.save()
    
    @classmethod
    def _reopen_order(cls, order, admin_user, notes: str):
        """Reopen order for revision."""
        # Return to previous state before dispute
        previous_state = order._state_before if hasattr(order, '_state_before') else 'delivered'
        
        order.state = previous_state
        order.dispute_reason = ''
        order.save()
    
    @classmethod
    def _reject_dispute(cls, order, admin_user, notes: str):
        """Reject dispute (no action)."""
        # Mark as completed (dispute rejected)
        order.state = 'completed'
        order.completed_at = timezone.now()
        order.save()
        
        # Release payment to writer
        if hasattr(order, 'payment'):
            from apps.payments.services.escrow_service import EscrowService
            EscrowService.release_escrow_funds(order.payment.id, admin_user)
    
    @classmethod
    def _log_resolution(cls, order, admin_user, resolution_type: str, 
                       refund_amount: Optional[float], notes: str):
        """Log dispute resolution for audit trail."""
        from apps.compliance.models import AuditLog
        
        AuditLog.objects.create(
            user=admin_user,
            action_type='update',
            model_name='Order',
            object_id=str(order.id),
            changes={
                'state': {'old': 'disputed', 'new': order.state},
                'resolution_type': resolution_type,
                'refund_amount': refund_amount,
                'resolution_notes': notes,
                'resolved_by': admin_user.email,
                'resolved_at': timezone.now().isoformat(),
            },
            before_state={'state': 'disputed'},
            after_state={'state': order.state},
        )
    
    @classmethod
    def _send_resolution_notifications(cls, order, admin_user, resolution_type: str, notes: str):
        """Send notifications about dispute resolution."""
        # Notify client
        send_order_notification.delay(
            user_id=order.client.id,
            order_id=order.id,
            notification_type='dispute_resolved',
            resolution_type=resolution_type,
            resolved_by=admin_user.get_full_name(),
            notes=notes,
        )
        
        # Notify writer
        send_order_notification.delay(
            user_id=order.writer.id,
            order_id=order.id,
            notification_type='dispute_resolved_writer',
            resolution_type=resolution_type,
            resolved_by=admin_user.get_full_name(),
            notes=notes,
        )
    
    @classmethod
    def get_dispute_metrics(cls, time_period_days: int = 30) -> Dict:
        """
        Get dispute statistics and metrics.
        
        Args:
            time_period_days: Time period for analysis
            
        Returns:
            Dictionary with dispute metrics
        """
        from django.db.models import Count, Avg, Q
        from django.utils import timezone
        
        time_period_ago = timezone.now() - timezone.timedelta(days=time_period_days)
        
        # Total disputes
        total_disputes = Order.objects.filter(state='disputed').count()
        
        # Recent disputes
        recent_disputes = Order.objects.filter(
            state='disputed',
            updated_at__gte=time_period_ago
        ).count()
        
        # Resolved disputes
        resolved_disputes = Order.objects.filter(
            state__in=['completed', 'refunded', 'cancelled'],
            updated_at__gte=time_period_ago
        ).filter(
            Q(dispute_reason__isnull=False) & ~Q(dispute_reason='')
        ).count()
        
        # Average resolution time
        resolved_orders = Order.objects.filter(
            state__in=['completed', 'refunded', 'cancelled'],
            updated_at__gte=time_period_ago
        ).filter(
            Q(dispute_reason__isnull=False) & ~Q(dispute_reason='')
        )
        
        avg_resolution_time = None
        if resolved_orders.exists():
            # Calculate average time from dispute to resolution
            # This would require tracking when dispute was raised
            pass
        
        # Dispute reasons breakdown
        reason_breakdown = dict(
            Order.objects.filter(
                state='disputed',
                updated_at__gte=time_period_ago
            ).values('dispute_reason')
            .annotate(count=Count('id'))
            .order_by('-count')
            .values_list('dispute_reason', 'count')
        )
        
        # Resolution type breakdown
        resolution_breakdown = {
            'full_refund': 0,
            'partial_refund': 0,
            'writer_payment': 0,
            'split_payment': 0,
            'reopen_order': 0,
            'no_action': 0,
        }
        
        # This would come from audit logs in production
        # For now, return placeholder
        
        return {
            'total_disputes': total_disputes,
            'recent_disputes': recent_disputes,
            'resolved_disputes': resolved_disputes,
            'resolution_rate': (
                (resolved_disputes / max(recent_disputes, 1)) * 100
                if recent_disputes > 0 else 0
            ),
            'avg_resolution_time': avg_resolution_time,
            'reason_breakdown': reason_breakdown,
            'resolution_breakdown': resolution_breakdown,
            'time_period_days': time_period_days,
        }