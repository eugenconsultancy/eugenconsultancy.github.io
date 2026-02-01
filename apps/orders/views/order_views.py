from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    CreateView, ListView, DetailView, UpdateView, DeleteView
)
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.db.models import Q
from django.db import models
from django.db.models import Count

from apps.orders.forms import OrderCreateForm, OrderUpdateForm
from apps.orders.models import Order
from apps.orders.services import OrderService


class ClientAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to ensure only clients can access the view."""
    
    def test_func(self):
        return self.request.user.is_client
    
    def handle_no_permission(self):
        messages.error(self.request, 'Access restricted to clients only.')
        return redirect('accounts:dashboard')


class OrderCreateView(ClientAccessMixin, CreateView):
    """View for clients to create new orders."""
    model = Order
    form_class = OrderCreateForm
    template_name = 'orders/create.html'
    success_url = reverse_lazy('orders:list')
    
    def form_valid(self, form):
        """Assign client to order. Initial state is set by model defaults."""
        order = form.save(commit=False)
        order.client = self.request.user
        
        # REMOVED: order.state = 'draft' 
        # django-fsm handles this via the model's 'default' attribute.
        
        order.save()
        
        messages.success(self.request, 'Order created successfully.')
        return redirect('orders:detail', pk=order.pk)
    
    def get_form_kwargs(self):
        """Pass request to form for validation."""
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def get_context_data(self, **kwargs):
        """Add pricing information to context."""
        context = super().get_context_data(**kwargs)
        
        # Calculate estimated prices (simplified)
        context['price_estimates'] = {
            'high_school': 15,
            'undergraduate': 25,
            'bachelors': 35,
            'masters': 50,
            'phd': 75,
            'professional': 60,
        }
        
        return context


class OrderListView(ClientAccessMixin, ListView):
    """View for clients to list their orders."""
    model = Order
    template_name = 'orders/list.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        """Return orders for the current client."""
        return Order.objects.filter(
            client=self.request.user
        ).select_related('writer').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        """Add order statistics to context."""
        context = super().get_context_data(**kwargs)
        
        queryset = self.get_queryset()
        
        # Calculate statistics
        total_orders = queryset.count()
        active_orders = queryset.filter(
            state__in=['paid', 'assigned', 'in_progress', 'delivered', 'revision_requested', 'in_revision']
        ).count()
        completed_orders = queryset.filter(state='completed').count()
        
        context.update({
            'total_orders': total_orders,
            'active_orders': active_orders,
            'completed_orders': completed_orders,
            'stats': self._get_order_stats(),
        })
        
        return context
    
    def _get_order_stats(self):
        """Get detailed order statistics."""
        user = self.request.user
        
        return {
            'by_state': dict(
                Order.objects.filter(client=user)
                .values('state')
                .annotate(count=Count('id'))
                .values_list('state', 'count')
            ),
            'by_academic_level': dict(
                Order.objects.filter(client=user)
                .values('academic_level')
                .annotate(count=Count('id'))
                .values_list('academic_level', 'count')
            ),
            'total_spent': Order.objects.filter(
                client=user,
                state='completed'
            ).aggregate(total=models.Sum('price'))['total'] or 0,
        }


class OrderDetailView(LoginRequiredMixin, DetailView):
    """View for viewing order details."""
    model = Order
    template_name = 'orders/detail.html'
    context_object_name = 'order'
    
    def get_queryset(self):
        """Return orders the user has access to."""
        user = self.request.user
        
        if user.is_staff:
            return Order.objects.all()
        
        # Clients can see their own orders
        # Writers can see orders assigned to them
        return Order.objects.filter(
            Q(client=user) | Q(writer=user)
        )
    
    def dispatch(self, request, *args, **kwargs):
        """Check if user has permission to view this order."""
        order = self.get_object()
        user = request.user
        
        if not (user.is_staff or order.client == user or order.writer == user):
            messages.error(request, 'You do not have permission to view this order.')
            return redirect('accounts:dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add additional context for order detail view."""
        context = super().get_context_data(**kwargs)
        order = self.object
        
        # Add files
        context['files'] = order.files.all()
        
        # Add delivery checklist if exists
        if hasattr(order, 'delivery_checklist'):
            context['checklist'] = order.delivery_checklist
        
        # Add payment information if client or admin
        if self.request.user == order.client or self.request.user.is_staff:
            if hasattr(order, 'payment'):
                context['payment'] = order.payment
        
        # Add available actions based on user role and order state
        context['available_actions'] = self._get_available_actions(order)
        
        # Add timeline events
        context['timeline'] = self._get_order_timeline(order)
        
        return context
    
    def _get_available_actions(self, order):
        """Get available actions based on user role and order state."""
        user = self.request.user
        actions = []
        
        if user == order.client:
            # Client actions
            if order.state == 'draft':
                actions.append(('pay', 'Pay for Order', 'btn-primary'))
            
            elif order.state == 'delivered':
                if order.can_request_revision:
                    actions.append(('request_revision', 'Request Revision', 'btn-warning'))
                actions.append(('complete', 'Mark as Complete', 'btn-success'))
            
            elif order.state in ['delivered', 'in_revision', 'revision_requested']:
                actions.append(('dispute', 'Raise Dispute', 'btn-danger'))
        
        elif user == order.writer:
            # Writer actions
            if order.state == 'assigned':
                actions.append(('start_work', 'Start Work', 'btn-primary'))
            
            elif order.state in ['in_progress', 'in_revision']:
                actions.append(('deliver', 'Deliver Work', 'btn-success'))
            
            elif order.state == 'revision_requested':
                actions.append(('accept_revision', 'Accept Revision Request', 'btn-warning'))
        
        elif user.is_staff:
            # Admin actions
            if order.state == 'paid' and not order.writer:
                actions.append(('assign_writer', 'Assign Writer', 'btn-primary'))
            
            elif order.state == 'disputed':
                actions.append(('resolve_dispute', 'Resolve Dispute', 'btn-info'))
        
        return actions
    
    def _get_order_timeline(self, order):
        """Create timeline of order events."""
        timeline = []
        
        # Order created
        timeline.append({
            'event': 'Order Created',
            'date': order.created_at,
            'icon': 'bi-plus-circle',
            'color': 'primary',
            'description': f'Order #{order.order_number} created',
        })
        
        # Paid
        if order.paid_at:
            timeline.append({
                'event': 'Payment Received',
                'date': order.paid_at,
                'icon': 'bi-credit-card',
                'color': 'success',
                'description': 'Payment processed and held in escrow',
            })
        
        # Assigned
        if order.assigned_at and order.writer:
            timeline.append({
                'event': 'Assigned to Writer',
                'date': order.assigned_at,
                'icon': 'bi-person-check',
                'color': 'info',
                'description': f'Assigned to {order.writer.get_full_name()}',
            })
        
        # Work started
        if order.started_at:
            timeline.append({
                'event': 'Work Started',
                'date': order.started_at,
                'icon': 'bi-play-circle',
                'color': 'warning',
                'description': 'Writer started working on the order',
            })
        
        # Delivered
        if order.delivered_at:
            timeline.append({
                'event': 'Work Delivered',
                'date': order.delivered_at,
                'icon': 'bi-check-circle',
                'color': 'success',
                'description': 'Writer delivered the completed work',
            })
        
        # Revisions
        if order.revision_count > 0:
            timeline.append({
                'event': f'Revision #{order.revision_count}',
                'date': order.delivered_at,  # Approximate
                'icon': 'bi-arrow-clockwise',
                'color': 'warning',
                'description': f'Revision requested by client',
            })
        
        # Completed
        if order.completed_at:
            timeline.append({
                'event': 'Order Completed',
                'date': order.completed_at,
                'icon': 'bi-flag',
                'color': 'success',
                'description': 'Order marked as completed by client',
            })
        
        # Cancelled
        if order.cancelled_at:
            timeline.append({
                'event': 'Order Cancelled',
                'date': order.cancelled_at,
                'icon': 'bi-x-circle',
                'color': 'danger',
                'description': 'Order was cancelled',
            })
        
        # Deadline
        timeline.append({
            'event': 'Deadline',
            'date': order.deadline,
            'icon': 'bi-calendar',
            'color': 'danger' if order.is_overdue else 'secondary',
            'description': 'Order deadline',
            'is_future': order.deadline > timezone.now(),
        })
        
        # Sort by date
        timeline.sort(key=lambda x: x['date'] or timezone.datetime.min)
        
        return timeline


class OrderUpdateView(ClientAccessMixin, UpdateView):
    """View for clients to update their orders."""
    model = Order
    form_class = OrderUpdateForm
    template_name = 'orders/update.html'
    
    def get_success_url(self):
        return reverse_lazy('orders:detail', kwargs={'pk': self.object.pk})
    
    def get_queryset(self):
        """Only allow updating draft orders."""
        return Order.objects.filter(
            client=self.request.user,
            state='draft'
        )
    
    def dispatch(self, request, *args, **kwargs):
        """Check if order can be updated."""
        order = self.get_object()
        
        if order.state != 'draft':
            messages.error(request, 'Only draft orders can be updated.')
            return redirect('orders:detail', pk=order.pk)
        
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Handle successful form submission."""
        messages.success(self.request, 'Order updated successfully.')
        return super().form_valid(form)


class OrderDeleteView(ClientAccessMixin, DeleteView):
    """View for clients to delete their orders."""
    model = Order
    template_name = 'orders/confirm_delete.html'
    success_url = reverse_lazy('orders:list')
    
    def get_queryset(self):
        """Only allow deleting draft orders."""
        return Order.objects.filter(
            client=self.request.user,
            state='draft'
        )
    
    def dispatch(self, request, *args, **kwargs):
        """Check if order can be deleted."""
        order = self.get_object()
        
        if order.state != 'draft':
            messages.error(request, 'Only draft orders can be deleted.')
            return redirect('orders:detail', pk=order.pk)
        
        return super().dispatch(request, *args, **kwargs)
    
    def delete(self, request, *args, **kwargs):
        """Handle successful deletion."""
        messages.success(request, 'Order deleted successfully.')
        return super().delete(request, *args, **kwargs)
    

class OrderPaymentView(LoginRequiredMixin, DetailView):
    """View for order payment."""
    model = Order
    template_name = 'orders/payment.html'
    context_object_name = 'order'
    
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add payment context if needed
        return context
    
class RevisionRequestView(LoginRequiredMixin, UpdateView):
    """Regular Django View for revision requests."""
    model = Order
    template_name = 'revisions/request_form.html'  # or 'orders/request_revision.html'
    fields = ['revision_instructions']
    
    def get_success_url(self):
        return reverse_lazy('orders:detail', kwargs={'pk': self.object.pk})
    
    def get_queryset(self):
        """Only allow clients to request revisions on their delivered orders."""
        return Order.objects.filter(
            client=self.request.user,
            state='delivered'
        )
    
    def form_valid(self, form):
        """Handle successful revision request."""
        order = form.save(commit=False)
        order.state = 'revision_requested'
        order.revision_count += 1
        order.save()
        
        messages.success(self.request, 'Revision requested successfully.')
        return super().form_valid(form)