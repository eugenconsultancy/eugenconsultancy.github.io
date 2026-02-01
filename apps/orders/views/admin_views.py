from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, TemplateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.db.models import Q, Count
from django.db import models

from apps.orders.models import Order
from apps.orders.forms import AdminAssignmentForm, DisputeResolutionForm
from apps.orders.services import AssignmentService, DisputeService


class AdminAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to ensure only admin users can access the view."""
    
    def test_func(self):
        return self.request.user.is_staff
    
    def handle_no_permission(self):
        messages.error(self.request, 'Access restricted to administrators only.')
        return redirect('accounts:dashboard')


class AdminOrderListView(AdminAccessMixin, ListView):
    """Admin view for listing all orders."""
    model = Order
    template_name = 'orders/admin/list.html'
    context_object_name = 'orders'
    paginate_by = 50
    
    def get_queryset(self):
        """Return filtered orders based on query parameters."""
        queryset = Order.objects.all().select_related('client', 'writer')
        
        # Apply filters
        state = self.request.GET.get('state')
        if state:
            queryset = queryset.filter(state=state)
        
        academic_level = self.request.GET.get('academic_level')
        if academic_level:
            queryset = queryset.filter(academic_level=academic_level)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search) |
                Q(title__icontains=search) |
                Q(client__email__icontains=search) |
                Q(writer__email__icontains=search)
            )
        
        # Order by creation date (newest first)
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        """Add statistics and filter options to context."""
        context = super().get_context_data(**kwargs)
        
        # Get order statistics
        total_orders = Order.objects.count()
        
        # Orders by state
        orders_by_state = dict(
            Order.objects.values('state')
            .annotate(count=Count('id'))
            .order_by('-count')
            .values_list('state', 'count')
        )
        
        # Recent activity
        recent_orders = Order.objects.order_by('-created_at')[:10]
        
        # Pending actions
        unassigned_orders = Order.objects.filter(
            state='paid',
            writer__isnull=True
        ).count()
        
        overdue_orders = Order.objects.filter(
            deadline__lt=timezone.now(),
            state__in=['assigned', 'in_progress', 'in_revision']
        ).count()
        
        disputed_orders = Order.objects.filter(state='disputed').count()
        
        context.update({
            'total_orders': total_orders,
            'orders_by_state': orders_by_state,
            'recent_orders': recent_orders,
            'unassigned_orders': unassigned_orders,
            'overdue_orders': overdue_orders,
            'disputed_orders': disputed_orders,
            'filter_state': self.request.GET.get('state', ''),
            'filter_search': self.request.GET.get('search', ''),
        })
        
        return context


class AdminOrderDetailView(AdminAccessMixin, DetailView):
    """Admin view for order details."""
    model = Order
    template_name = 'orders/admin/detail.html'
    context_object_name = 'order'
    
    def get_queryset(self):
        """Return all orders for admin view."""
        return Order.objects.all().select_related(
            'client', 'writer', 'assigned_by'
        )
    
    def get_context_data(self, **kwargs):
        """Add admin actions and detailed information to context."""
        context = super().get_context_data(**kwargs)
        order = self.object
        
        # Get all files
        context['files'] = order.files.all()
        
        # Get payment information
        if hasattr(order, 'payment'):
            context['payment'] = order.payment
        
        # Get delivery checklist
        if hasattr(order, 'delivery_checklist'):
            context['checklist'] = order.delivery_checklist
        
        # Get all communications (would be from messaging app)
        context['communications'] = []  # Placeholder
        
        # Get audit logs
        from apps.compliance.models import AuditLog
        context['audit_logs'] = AuditLog.objects.filter(
            model_name='Order',
            object_id=str(order.id)
        ).order_by('-timestamp')[:20]
        
        # Available admin actions
        context['admin_actions'] = self._get_admin_actions(order)
        
        # Writer assignment form if needed
        if order.state == 'paid' and not order.writer:
            context['assignment_form'] = AdminAssignmentForm()
        
        # Dispute resolution form if needed
        if order.state == 'disputed':
            context['dispute_form'] = DisputeResolutionForm()
        
        return context
    
    def _get_admin_actions(self, order):
        """Get available admin actions for this order."""
        actions = []
        
        if order.state == 'paid' and not order.writer:
            actions.append(('assign', 'Assign Writer', 'btn-primary'))
        
        if order.state == 'held_in_escrow' and order.payment:
            actions.append(('release_escrow', 'Release Escrow', 'btn-success'))
        
        if order.state == 'disputed':
            actions.append(('resolve_dispute', 'Resolve Dispute', 'btn-info'))
        
        if order.state in ['delivered', 'revision_requested']:
            actions.append(('force_complete', 'Force Complete', 'btn-warning'))
        
        if order.state not in ['completed', 'cancelled', 'refunded']:
            actions.append(('cancel', 'Cancel Order', 'btn-danger'))
        
        return actions


class OrderAssignmentAdminView(AdminAccessMixin, TemplateView):
    """Admin view for assigning orders to writers."""
    template_name = 'orders/admin/assignment.html'
    
    def get_context_data(self, **kwargs):
        """Get context for order assignment."""
        context = super().get_context_data(**kwargs)
        
        # Get unassigned orders
        unassigned_orders = Order.objects.filter(
            state='paid',
            writer__isnull=True,
            deadline__gt=timezone.now(),
        ).select_related('client').order_by('deadline')
        
        # Get available writers
        from apps.accounts.models import User
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
        ).order_by('writer_profile__current_orders', '-writer_profile__average_rating')
        
        # Get assignment statistics
        assignment_stats = {
            'unassigned_orders': unassigned_orders.count(),
            'available_writers': available_writers.count(),
            'avg_writer_load': self._calculate_avg_writer_load(),
        }
        
        context.update({
            'unassigned_orders': unassigned_orders,
            'available_writers': available_writers,
            'assignment_form': AdminAssignmentForm(),
            'assignment_stats': assignment_stats,
        })
        
        return context
    
    def _calculate_avg_writer_load(self):
        """Calculate average writer workload."""
        from apps.accounts.models import WriterProfile
        
        active_writers = WriterProfile.objects.filter(
            is_available=True,
            status='active',
        )
        
        if not active_writers.exists():
            return 0
        
        total_load = sum(w.current_orders for w in active_writers)
        avg_load = total_load / active_writers.count()
        
        return round(avg_load, 2)
    
    def post(self, request, *args, **kwargs):
        """Handle order assignment."""
        form = AdminAssignmentForm(request.POST)
        
        if form.is_valid():
            try:
                # Use assignment service
                AssignmentService.assign_order_to_writer(
                    order_id=form.cleaned_data['order_id'],
                    writer_id=form.cleaned_data['writer_id'],
                    admin_user=request.user,
                )
                
                messages.success(request, 'Order assigned successfully.')
                
            except Exception as e:
                messages.error(request, f'Error assigning order: {str(e)}')
        
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        return redirect('orders:admin_assignment')


class OrderDisputeView(AdminAccessMixin, DetailView):
    """Admin view for resolving order disputes."""
    model = Order
    template_name = 'orders/admin/dispute.html'
    context_object_name = 'order'
    
    def get_queryset(self):
        """Return disputed orders."""
        return Order.objects.filter(state='disputed')
    
    def dispatch(self, request, *args, **kwargs):
        """Check if order is in disputed state."""
        order = self.get_object()
        
        if order.state != 'disputed':
            messages.error(request, 'This order is not in dispute.')
            return redirect('orders:admin_detail', pk=order.pk)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add dispute information and resolution form."""
        context = super().get_context_data(**kwargs)
        order = self.object
        
        # Get dispute details
        context['dispute_details'] = {
            'reason': order.dispute_reason,
            'raised_by': order.client,
            'raised_at': order.updated_at,  # When state changed to disputed
        }
        
        # Get order timeline
        from apps.compliance.models import AuditLog
        dispute_logs = AuditLog.objects.filter(
            model_name='Order',
            object_id=str(order.id),
            action_type='update',
            changes__icontains='disputed'
        ).order_by('-timestamp')
        
        context['dispute_logs'] = dispute_logs
        
        # Get resolution form
        context['resolution_form'] = DisputeResolutionForm()
        
        # Get available resolutions
        context['resolution_options'] = [
            ('full_refund', 'Full Refund to Client', 
             'Refund 100% of payment to client'),
            ('partial_refund', 'Partial Refund',
             f'Refund {order.price * 0.5} (50%) to client'),
            ('writer_payment', 'Pay Writer',
             'Release escrow funds to writer'),
            ('split_payment', 'Split Payment',
             'Split payment between client and writer'),
            ('reopen_order', 'Reopen Order',
             'Return order to previous state for revision'),
        ]
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle dispute resolution."""
        order = self.get_object()
        form = DisputeResolutionForm(request.POST)
        
        if form.is_valid():
            try:
                # Use dispute service to resolve
                DisputeService.resolve_dispute(
                    order_id=order.id,
                    admin_user=request.user,
                    resolution_type=form.cleaned_data['resolution_type'],
                    refund_amount=form.cleaned_data.get('refund_amount'),
                    notes=form.cleaned_data.get('notes', ''),
                )
                
                messages.success(request, 'Dispute resolved successfully.')
                
                return redirect('orders:admin_detail', pk=order.pk)
                
            except Exception as e:
                messages.error(request, f'Error resolving dispute: {str(e)}')
        
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        return self.get(request, *args, **kwargs)