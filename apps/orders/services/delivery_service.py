from typing import Dict, List, Optional
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.conf import settings
from django.db import models


from apps.orders.models import Order, OrderFile, DeliveryChecklist
from apps.accounts.services.document_validator import DocumentValidator
from apps.notifications.tasks import send_order_notification


class DeliveryService:
    """Service for handling order deliveries."""
    
    @classmethod
    @transaction.atomic
    def deliver_order(
        cls,
        order_id: int,
        writer_id: int,
        files: List,
        notes: str = '',
        checklist_data: Optional[Dict] = None
    ) -> Order:
        """
        Deliver completed work for an order.
        
        Args:
            order_id: ID of the order to deliver
            writer_id: ID of the writer delivering
            files: List of uploaded files
            notes: Delivery notes
            checklist_data: Delivery checklist data
            
        Returns:
            Updated Order object
        
        Raises:
            ValidationError: If delivery cannot be performed
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            order = Order.objects.select_for_update().get(id=order_id)
            writer = User.objects.get(id=writer_id)
            
            # Validate permissions
            if order.writer != writer:
                raise ValidationError("You are not assigned to this order.")
            
            # Check if order can be delivered
            if order.state not in ['in_progress', 'in_revision']:
                raise ValidationError(f"Cannot deliver order in state: {order.state}")
            
            # Validate files
            if not files:
                raise ValidationError("At least one file is required for delivery.")
            
            # Process delivery
            order.deliver()
            order.save()
            
            # Save files
            cls._save_delivery_files(order, writer, files, notes)
            
            # Update delivery checklist
            if checklist_data:
                cls._update_checklist(order, checklist_data)
            
            # Log delivery
            cls._log_delivery(order, writer, notes)
            
            # Send notifications
            cls._send_delivery_notifications(order, writer)
            
            return order
            
        except (Order.DoesNotExist, User.DoesNotExist) as e:
            raise ValidationError(f"Invalid order or writer: {str(e)}")
    
    @classmethod
    def _save_delivery_files(cls, order, writer, files, notes: str):
        """Save delivery files with validation."""
        for file_obj in files:
            # Validate file
            try:
                validation_result = DocumentValidator.validate_file(file_obj)
            except ValidationError as e:
                raise ValidationError(f"File validation failed: {str(e)}")
            
            # Create order file record
            order_file = OrderFile(
                order=order,
                uploaded_by=writer,
                file_type='submission',
                description=notes or f'Delivery for order #{order.order_number}',
                original_filename=validation_result['original_filename'],
                file_size=validation_result['file_size'],
                mime_type=validation_result['mime_type'],
                file_hash=validation_result['file_hash'],
                version=order.revision_count + 1,
                is_final=True if order.state != 'in_revision' else False,
            )
            
            # Perform virus scan
            if hasattr(settings, 'ENABLE_VIRUS_SCAN') and settings.ENABLE_VIRUS_SCAN:
                from django.core.files.storage import default_storage
                
                temp_path = f'temp/delivery_{timezone.now().timestamp()}_{file_obj.name}'
                with default_storage.open(temp_path, 'wb') as temp_file:
                    for chunk in file_obj.chunks():
                        temp_file.write(chunk)
                
                is_clean, scan_result = DocumentValidator.virus_scan_file(
                    default_storage.path(temp_path)
                )
                
                order_file.scanned_for_virus = True
                order_file.scan_result = scan_result
                
                # Delete temporary file
                default_storage.delete(temp_path)
                
                if not is_clean:
                    raise ValidationError(f"File failed virus scan: {scan_result}")
            
            # Save file
            order_file.file.save(file_obj.name, file_obj, save=False)
            order_file.save()
    
    @classmethod
    def _update_checklist(cls, order, checklist_data: Dict):
        """Update delivery checklist."""
        checklist, created = DeliveryChecklist.objects.get_or_create(order=order)
        
        # Update checklist fields
        for field, value in checklist_data.items():
            if hasattr(checklist, field):
                setattr(checklist, field, value)
        
        # Mark as passed if all critical items are checked
        critical_fields = [
            'formatting_correct',
            'instructions_followed',
            'plagiarism_free',
            'grammar_correct',
        ]
        
        if all(getattr(checklist, field, False) for field in critical_fields):
            checklist.passed_quality_check = True
        
        checklist.save()
    
    @classmethod
    def _log_delivery(cls, order, writer, notes: str):
        """Log delivery for audit trail."""
        from apps.compliance.models import AuditLog
        
        AuditLog.objects.create(
            user=writer,
            action_type='update',
            model_name='Order',
            object_id=str(order.id),
            changes={
                'state': {'old': order._state_before, 'new': 'delivered'},
                'delivered_at': timezone.now().isoformat(),
                'notes': notes,
            },
            before_state={'state': order._state_before},
            after_state={'state': 'delivered'},
        )
    
    @classmethod
    def _send_delivery_notifications(cls, order, writer):
        """Send notifications about delivery."""
        # Notify client
        send_order_notification.delay(
            user_id=order.client.id,
            order_id=order.id,
            notification_type='order_delivered',
            writer_name=writer.get_full_name(),
            deadline=order.deadline.isoformat(),
        )
        
        # Notify admins if overdue
        if order.is_overdue:
            cls._notify_admins_of_overdue_delivery(order, writer)
    
    @classmethod
    def _notify_admins_of_overdue_delivery(cls, order, writer):
        """Notify admins of overdue delivery."""
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
                notification_type='overdue_delivery',
                writer_name=writer.get_full_name(),
                writer_email=writer.email,
                order_title=order.title,
                overdue_by=str(order.time_remaining),  # Negative time remaining
            )
    
    @classmethod
    def request_revision(
        cls,
        order_id: int,
        client_id: int,
        reason: str,
        revision_details: str = ''
    ) -> Order:
        """
        Request revision for delivered work.
        
        Args:
            order_id: ID of the order
            client_id: ID of the client requesting revision
            reason: Reason for revision
            revision_details: Detailed revision requirements
            
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
            
            # Check if revision can be requested
            if order.state != 'delivered':
                raise ValidationError(f"Cannot request revision for order in state: {order.state}")
            
            if order.revision_count >= order.max_revisions:
                raise ValidationError(
                    f"Maximum revision limit ({order.max_revisions}) reached."
                )
            
            # Request revision
            order.request_revision(reason)
            order.save()
            
            # Log revision request
            cls._log_revision_request(order, client, reason, revision_details)
            
            # Send notifications
            cls._send_revision_notifications(order, client, reason)
            
            return order
            
        except (Order.DoesNotExist, User.DoesNotExist) as e:
            raise ValidationError(f"Invalid order or client: {str(e)}")
    
    @classmethod
    def _log_revision_request(cls, order, client, reason: str, details: str):
        """Log revision request for audit trail."""
        from apps.compliance.models import AuditLog
        
        AuditLog.objects.create(
            user=client,
            action_type='update',
            model_name='Order',
            object_id=str(order.id),
            changes={
                'state': {'old': 'delivered', 'new': 'revision_requested'},
                'revision_count': order.revision_count,
                'reason': reason,
                'details': details,
            },
            before_state={'state': 'delivered', 'revision_count': order.revision_count - 1},
            after_state={'state': 'revision_requested', 'revision_count': order.revision_count},
        )
    
    @classmethod
    def _send_revision_notifications(cls, order, client, reason: str):
        """Send notifications about revision request."""
        # Notify writer
        send_order_notification.delay(
            user_id=order.writer.id,
            order_id=order.id,
            notification_type='revision_requested',
            client_name=client.get_full_name(),
            reason=reason,
            revision_number=order.revision_count,
            max_revisions=order.max_revisions,
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
                notification_type='admin_revision_request',
                client_name=client.get_full_name(),
                writer_name=order.writer.get_full_name(),
                reason=reason,
            )
    
    @classmethod
    def complete_order(cls, order_id: int, client_id: int) -> Order:
        """
        Mark order as completed.
        
        Args:
            order_id: ID of the order
            client_id: ID of the client completing
            
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
            
            # Check if order can be completed
            if order.state != 'delivered':
                raise ValidationError(f"Cannot complete order in state: {order.state}")
            
            # Complete order
            if order.revision_count == 0:
                order.complete_without_revision()
            else:
                order.complete_after_revision()
            
            order.save()
            
            # Log completion
            cls._log_completion(order, client)
            
            # Send notifications
            cls._send_completion_notifications(order, client)
            
            return order
            
        except (Order.DoesNotExist, User.DoesNotExist) as e:
            raise ValidationError(f"Invalid order or client: {str(e)}")
    
    @classmethod
    def _log_completion(cls, order, client):
        """Log order completion for audit trail."""
        from apps.compliance.models import AuditLog
        
        AuditLog.objects.create(
            user=client,
            action_type='update',
            model_name='Order',
            object_id=str(order.id),
            changes={
                'state': {'old': 'delivered', 'new': 'completed'},
                'completed_at': timezone.now().isoformat(),
            },
            before_state={'state': 'delivered'},
            after_state={'state': 'completed'},
        )
    
    @classmethod
    def _send_completion_notifications(cls, order, client):
        """Send notifications about order completion."""
        # Notify writer
        send_order_notification.delay(
            user_id=order.writer.id,
            order_id=order.id,
            notification_type='order_completed',
            client_name=client.get_full_name(),
            order_price=str(order.price),
            writer_payment=str(order.writer_payment),
        )
        
        # Notify admins (for escrow release)
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
                notification_type='admin_order_completed',
                client_name=client.get_full_name(),
                writer_name=order.writer.get_full_name(),
                order_price=str(order.price),
            )
    
    @classmethod
    def get_delivery_metrics(cls, writer_id: Optional[int] = None) -> Dict:
        """
        Get delivery performance metrics.
        
        Args:
            writer_id: Optional writer ID to filter by
            
        Returns:
            Dictionary with delivery metrics
        """
        from django.db.models import Count, Avg, Q
        from django.utils import timezone
        
        # Base queryset
        orders = Order.objects.filter(state='completed')
        
        if writer_id:
            orders = orders.filter(writer_id=writer_id)
        
        # Calculate metrics
        total_deliveries = orders.count()
        
        if total_deliveries == 0:
            return {
                'total_deliveries': 0,
                'avg_delivery_time': None,
                'on_time_rate': 0,
                'revision_rate': 0,
                'completion_rate': 0,
            }
        
        # Average delivery time (from assignment to delivery)
        avg_delivery_time = orders.annotate(
            delivery_time=models.F('delivered_at') - models.F('assigned_at')
        ).aggregate(
            avg_time=Avg('delivery_time')
        )['avg_time']
        
        # On-time delivery rate
        on_time = orders.filter(delivered_at__lte=models.F('deadline')).count()
        on_time_rate = (on_time / total_deliveries) * 100
        
        # Revision rate
        with_revisions = orders.filter(revision_count__gt=0).count()
        revision_rate = (with_revisions / total_deliveries) * 100
        
        # Recent performance (last 30 days)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        recent_orders = orders.filter(completed_at__gte=thirty_days_ago)
        recent_count = recent_orders.count()
        
        recent_on_time = recent_orders.filter(
            delivered_at__lte=models.F('deadline')
        ).count()
        
        recent_on_time_rate = (
            (recent_on_time / recent_count * 100) if recent_count > 0 else 0
        )
        
        return {
            'total_deliveries': total_deliveries,
            'avg_delivery_time': avg_delivery_time,
            'on_time_rate': round(on_time_rate, 1),
            'revision_rate': round(revision_rate, 1),
            'recent_on_time_rate': round(recent_on_time_rate, 1),
            'recent_period_days': 30,
            'recent_order_count': recent_count,
        }