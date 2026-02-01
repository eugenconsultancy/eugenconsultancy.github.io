from typing import Dict, Optional
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models

from apps.orders.models import Order
from apps.notifications.tasks import send_order_notification


class AssignmentService:
    """Service for handling order assignments to writers."""
    
    @classmethod
    @transaction.atomic
    def assign_order_to_writer(
        cls,
        order_id: int,
        writer_id: int,
        admin_user=None,
        notes: str = ''
    ) -> Order:
        """
        Assign an order to a writer.
        
        Args:
            order_id: ID of the order to assign
            writer_id: ID of the writer to assign to
            admin_user: Admin user performing assignment (None for self-assignment)
            notes: Assignment notes
            
        Returns:
            Updated Order object
        
        Raises:
            ValidationError: If assignment cannot be performed
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            order = Order.objects.select_for_update().get(id=order_id)
            writer = User.objects.get(id=writer_id)
            
            if not writer.is_writer:
                raise ValidationError("User is not a writer.")
            
            # Check if writer is approved
            if not writer.verification_status.is_approved:
                raise ValidationError("Writer is not approved.")
            
            # Check if writer can accept orders
            if not writer.writer_profile.can_accept_orders:
                raise ValidationError("Writer is not available for new assignments.")
            
            # Check if order can be assigned
            if order.state != 'paid':
                raise ValidationError(f"Cannot assign order in state: {order.state}")
            
            if order.writer:
                raise ValidationError("Order is already assigned to a writer.")
            
            # Check if writer has required expertise
            if not cls._has_required_expertise(order, writer):
                raise ValidationError(
                    "Writer's specialization does not match order requirements."
                )
            
            # Perform assignment
            if admin_user:
                order.assign_to_writer(admin_user, writer)
            else:
                # Self-assignment (writer accepting order)
                order.writer = writer
                order.assigned_at = timezone.now()
                order.state = 'assigned'
            
            order.save()
            
            # Update writer's current order count
            writer.writer_profile.current_orders += 1
            writer.writer_profile.save()
            
            # Log the assignment
            cls._log_assignment(order, writer, admin_user, notes)
            
            # Send notifications
            cls._send_assignment_notifications(order, writer, admin_user)
            
            return order
            
        except (Order.DoesNotExist, User.DoesNotExist) as e:
            raise ValidationError(f"Invalid order or writer: {str(e)}")
    
    @classmethod
    def _has_required_expertise(cls, order, writer) -> bool:
        """Check if writer has required expertise for the order."""
        if not writer.writer_profile.specialization:
            return True  # Writer hasn't specified specialization
        
        writer_specializations = [
            s.strip().lower() 
            for s in writer.writer_profile.specialization.split(',')
        ]
        
        order_subject = order.subject.lower()
        
        # Check if any specialization matches the order subject
        for spec in writer_specializations:
            if spec in order_subject or order_subject in spec:
                return True
        
        # Check academic level compatibility
        writer_education = writer.writer_profile.education_level
        order_level = order.academic_level
        
        # Map education levels to capability
        level_capability = {
            'high_school': ['high_school'],
            'bachelors': ['high_school', 'undergraduate', 'bachelors'],
            'masters': ['high_school', 'undergraduate', 'bachelors', 'masters'],
            'phd': ['high_school', 'undergraduate', 'bachelors', 'masters', 'phd', 'professional'],
            'professor': ['high_school', 'undergraduate', 'bachelors', 'masters', 'phd', 'professional'],
        }
        
        capable_levels = level_capability.get(writer_education, [])
        return order_level in capable_levels
    
    @classmethod
    def _log_assignment(cls, order, writer, admin_user, notes: str):
        """Log assignment for audit trail."""
        from apps.compliance.models import AuditLog
        
        action_type = 'admin_assignment' if admin_user else 'self_assignment'
        
        AuditLog.objects.create(
            user=admin_user or writer,
            action_type='update',
            model_name='Order',
            object_id=str(order.id),
            changes={
                'writer': {'old': None, 'new': writer.email},
                'state': {'old': 'paid', 'new': 'assigned'},
                'assignment_type': action_type,
                'notes': notes,
            },
            before_state={'writer': None, 'state': 'paid'},
            after_state={'writer': writer.email, 'state': 'assigned'},
        )
    
    @classmethod
    def _send_assignment_notifications(cls, order, writer, admin_user):
        """Send notifications about assignment."""
        # Notify writer
        send_order_notification.delay(
            user_id=writer.id,
            order_id=order.id,
            notification_type='order_assigned',
            assigned_by=admin_user.get_full_name() if admin_user else 'System',
            deadline=order.deadline.isoformat(),
        )
        
        # Notify client
        send_order_notification.delay(
            user_id=order.client.id,
            order_id=order.id,
            notification_type='writer_assigned',
            writer_name=writer.get_full_name(),
            writer_email=writer.email,
        )
        
        # Notify admin if self-assignment
        if not admin_user:
            cls._notify_admins_of_self_assignment(order, writer)
    
    @classmethod
    def _notify_admins_of_self_assignment(cls, order, writer):
        """Notify admins of self-assignment."""
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
                notification_type='self_assignment',
                writer_name=writer.get_full_name(),
                writer_email=writer.email,
                order_title=order.title,
            )
    
    @classmethod
    def get_available_writers_for_order(cls, order_id: int) -> Dict:
        """
        Get list of available writers for an order.
        
        Args:
            order_id: ID of the order
            
        Returns:
            Dictionary with available writers and match scores
        """
        from django.contrib.auth import get_user_model
        from django.db.models import Q, Count
        User = get_user_model()
        
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return {'error': 'Order not found'}
        
        # Get available writers
        available_writers = User.objects.filter(
            user_type='writer',
            writer_profile__is_available=True,
            verification_status__state='approved',
        ).select_related('writer_profile').annotate(
            current_orders=Count('writer_orders', filter=Q(
                writer_orders__state__in=['assigned', 'in_progress', 'in_revision']
            ))
        ).filter(
            writer_profile__current_orders__lt=models.F('writer_profile__max_orders')
        )
        
        # Calculate match scores
        writers_with_scores = []
        for writer in available_writers:
            score = cls._calculate_match_score(order, writer)
            
            if score > 0:  # Only include writers with some match
                writers_with_scores.append({
                    'writer': writer,
                    'score': score,
                    'match_reasons': cls._get_match_reasons(order, writer),
                    'current_load': writer.writer_profile.current_orders,
                    'max_load': writer.writer_profile.max_orders,
                    'rating': writer.writer_profile.average_rating,
                    'completion_rate': writer.writer_profile.success_rate,
                })
        
        # Sort by score (highest first)
        writers_with_scores.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            'order': order,
            'total_available': len(writers_with_scores),
            'writers': writers_with_scores[:20],  # Limit to top 20
        }
    
    @classmethod
    def _calculate_match_score(cls, order, writer) -> float:
        """Calculate match score between order and writer."""
        score = 0.0
        
        # 1. Specialization match (40%)
        if writer.writer_profile.specialization:
            writer_specializations = [
                s.strip().lower() 
                for s in writer.writer_profile.specialization.split(',')
            ]
            
            order_subject = order.subject.lower()
            
            for spec in writer_specializations:
                if spec in order_subject or order_subject in spec:
                    score += 40
                    break
        
        # 2. Academic level compatibility (30%)
        writer_education = writer.writer_profile.education_level
        order_level = order.academic_level
        
        level_capability = {
            'high_school': ['high_school'],
            'bachelors': ['high_school', 'undergraduate', 'bachelors'],
            'masters': ['high_school', 'undergraduate', 'bachelors', 'masters'],
            'phd': ['high_school', 'undergraduate', 'bachelors', 'masters', 'phd', 'professional'],
            'professor': ['high_school', 'undergraduate', 'bachelors', 'masters', 'phd', 'professional'],
        }
        
        capable_levels = level_capability.get(writer_education, [])
        if order_level in capable_levels:
            score += 30
        
        # 3. Writer rating (20%)
        rating = writer.writer_profile.average_rating
        score += (rating / 5.0) * 20
        
        # 4. Current load (10%)
        current_load = writer.writer_profile.current_orders
        max_load = writer.writer_profile.max_orders
        load_percentage = current_load / max_load if max_load > 0 else 0
        score += (1 - load_percentage) * 10
        
        return round(score, 2)
    
    @classmethod
    def _get_match_reasons(cls, order, writer) -> list:
        """Get reasons why writer matches the order."""
        reasons = []
        
        # Check specialization
        if writer.writer_profile.specialization:
            writer_specializations = [
                s.strip().lower() 
                for s in writer.writer_profile.specialization.split(',')
            ]
            
            order_subject = order.subject.lower()
            
            for spec in writer_specializations:
                if spec in order_subject or order_subject in spec:
                    reasons.append(f"Specialization in {spec}")
                    break
        
        # Check education level
        writer_education = writer.writer_profile.education_level
        if writer_education:
            education_display = writer.writer_profile.get_education_level_display()
            reasons.append(f"{education_display} level education")
        
        # Check rating
        if writer.writer_profile.average_rating >= 4.0:
            reasons.append(f"High rating ({writer.writer_profile.average_rating}/5.0)")
        
        # Check completion rate
        if writer.writer_profile.success_rate >= 90:
            reasons.append("High completion rate")
        
        return reasons
    
    @classmethod
    def auto_assign_orders(cls) -> Dict:
        """
        Automatically assign orders to suitable writers.
        
        Returns:
            Dictionary with assignment results
        """
        results = {
            'total_processed': 0,
            'assigned': 0,
            'failed': 0,
            'assignments': [],
        }
        
        # Get unassigned orders
        unassigned_orders = Order.objects.filter(
            state='paid',
            writer__isnull=True,
            deadline__gt=timezone.now() - timezone.timedelta(hours=24),  # Not too old
        ).order_by('deadline')[:50]  # Limit batch size
        
        for order in unassigned_orders:
            try:
                # Get best matching writer
                available_writers = cls.get_available_writers_for_order(order.id)
                
                if available_writers.get('writers'):
                    best_writer = available_writers['writers'][0]['writer']
                    
                    # Assign if match score is high enough
                    if available_writers['writers'][0]['score'] >= 60:
                        cls.assign_order_to_writer(
                            order_id=order.id,
                            writer_id=best_writer.id,
                            admin_user=None,  # System assignment
                            notes='Automatically assigned by system'
                        )
                        
                        results['assigned'] += 1
                        results['assignments'].append({
                            'order_id': order.id,
                            'order_number': order.order_number,
                            'writer_id': best_writer.id,
                            'writer_email': best_writer.email,
                            'match_score': available_writers['writers'][0]['score'],
                        })
                
                results['total_processed'] += 1
                
            except Exception as e:
                results['failed'] += 1
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to auto-assign order {order.id}: {str(e)}")
        
        return results