from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.utils import timezone
from django.db.models import Count, Q

from apps.orders.models import Order
from apps.payments.models import Payment
from apps.compliance.models import DataRequest


class DashboardView(LoginRequiredMixin, TemplateView):
    """User dashboard view."""
    template_name = 'accounts/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user-specific data
        if user.is_client:
            context.update(self._get_client_context(user))
        elif user.is_writer:
            context.update(self._get_writer_context(user))
        elif user.is_admin_or_staff:
            context.update(self._get_admin_context(user))
        
        # Common context for all users
        context.update({
            'user': user,
            'current_time': timezone.now(),
            'notifications': self._get_user_notifications(user),
        })
        
        return context
    
    def _get_client_context(self, user):
        """Get context data for client users."""
        # Get active orders
        active_orders = Order.objects.filter(
            client=user,
            state__in=['paid', 'assigned', 'in_progress', 'delivered', 'revision_requested', 'in_revision']
        ).order_by('-created_at')[:5]
        
        # Get completed orders
        completed_orders = Order.objects.filter(
            client=user,
            state='completed'
        ).order_by('-completed_at')[:5]
        
        # Get pending payments
        pending_payments = Payment.objects.filter(
            user=user,
            state__in=['processing', 'held_in_escrow']
        ).order_by('-created_at')[:5]
        
        # Statistics
        total_orders = Order.objects.filter(client=user).count()
        completed_count = Order.objects.filter(client=user, state='completed').count()
        active_count = active_orders.count()
        
        return {
            'user_type': 'client',
            'active_orders': active_orders,
            'completed_orders': completed_orders,
            'pending_payments': pending_payments,
            'stats': {
                'total_orders': total_orders,
                'completed_orders': completed_count,
                'active_orders': active_count,
                'completion_rate': (completed_count / total_orders * 100) if total_orders > 0 else 0,
            },
        }
    
    def _get_writer_context(self, user):
        """Get context data for writer users."""
        # Get assigned orders
        assigned_orders = Order.objects.filter(
            writer=user,
            state__in=['assigned', 'in_progress', 'in_revision']
        ).order_by('deadline')[:5]
        
        # Get available orders (for bidding)
        available_orders = Order.objects.filter(
            state='paid',
            writer__isnull=True,
            deadline__gt=timezone.now()
        ).exclude(
            Q(client=user)  # Don't show writer's own orders
        ).order_by('-created_at')[:5]
        
        # Get completed orders
        completed_orders = Order.objects.filter(
            writer=user,
            state='completed'
        ).order_by('-completed_at')[:5]
        
        # Get pending payments
        pending_payments = Payment.objects.filter(
            order__writer=user,
            state='held_in_escrow'
        ).select_related('order').order_by('-created_at')[:5]
        
        # Writer profile stats
        writer_profile = user.writer_profile
        verification_status = user.verification_status
        
        return {
            'user_type': 'writer',
            'assigned_orders': assigned_orders,
            'available_orders': available_orders,
            'completed_orders': completed_orders,
            'pending_payments': pending_payments,
            'writer_profile': writer_profile,
            'verification_status': verification_status,
            'stats': {
                'current_orders': writer_profile.current_orders,
                'max_orders': writer_profile.max_orders,
                'completed_orders': writer_profile.completed_orders,
                'total_earnings': writer_profile.total_earnings,
                'average_rating': writer_profile.average_rating,
                'verification_state': verification_status.get_state_display(),
            },
        }
    
    def _get_admin_context(self, user):
        """Get context data for admin users."""
        # Platform-wide statistics
        total_orders = Order.objects.count()
        active_orders = Order.objects.filter(
            state__in=['paid', 'assigned', 'in_progress', 'delivered', 'revision_requested', 'in_revision']
        ).count()
        
        total_writers = user._meta.model.objects.filter(user_type='writer').count()
        pending_verifications = user.verification_status.objects.filter(state='documents_submitted').count()
        
        # Recent activities
        recent_orders = Order.objects.order_by('-created_at')[:10]
        recent_payments = Payment.objects.order_by('-created_at')[:10]
        
        # Pending data requests
        pending_requests = DataRequest.objects.filter(
            status__in=['received', 'verifying', 'processing']
        ).count()
        
        return {
            'user_type': 'admin',
            'recent_orders': recent_orders,
            'recent_payments': recent_payments,
            'stats': {
                'total_orders': total_orders,
                'active_orders': active_orders,
                'total_writers': total_writers,
                'pending_verifications': pending_verifications,
                'pending_requests': pending_requests,
            },
        }
    
    def _get_user_notifications(self, user):
        """Get user notifications."""
        # In production, this would come from a notifications model
        # For now, return mock notifications based on user state
        notifications = []
        
        if user.is_writer:
            verification = user.verification_status
            
            if verification.state == 'documents_submitted':
                notifications.append({
                    'type': 'info',
                    'title': 'Verification Pending',
                    'message': 'Your documents are under review. You will be notified once approved.',
                    'timestamp': timezone.now(),
                })
            elif verification.state == 'revision_required':
                notifications.append({
                    'type': 'warning',
                    'title': 'Revision Required',
                    'message': 'Please review the admin notes and update your documents.',
                    'timestamp': timezone.now(),
                })
            
            # Check for nearing deadlines
            nearing_deadlines = Order.objects.filter(
                writer=user,
                state__in=['assigned', 'in_progress', 'in_revision'],
                deadline__lte=timezone.now() + timezone.timedelta(hours=24),
                deadline__gt=timezone.now(),
            ).exists()
            
            if nearing_deadlines:
                notifications.append({
                    'type': 'warning',
                    'title': 'Approaching Deadlines',
                    'message': 'You have orders with deadlines within 24 hours.',
                    'timestamp': timezone.now(),
                })
        
        elif user.is_client:
            # Check for orders needing attention
            revision_requests = Order.objects.filter(
                client=user,
                state='revision_requested'
            ).exists()
            
            if revision_requests:
                notifications.append({
                    'type': 'info',
                    'title': 'Revision Available',
                    'message': 'You have orders waiting for your revision request.',
                    'timestamp': timezone.now(),
                })
        
        return notifications