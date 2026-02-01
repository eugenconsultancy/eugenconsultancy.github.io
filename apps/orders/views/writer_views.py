from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, TemplateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.db.models import Q

from apps.orders.models import Order
from apps.orders.forms import DeliveryForm, RevisionResponseForm
from apps.orders.services import AssignmentService, DeliveryService


class WriterAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to ensure only approved writers can access the view."""
    
    def test_func(self):
        user = self.request.user
        if not user.is_writer:
            return False
        
        # Check if writer is approved
        if hasattr(user, 'verification_status'):
            return user.verification_status.is_approved
        
        return False
    
    def handle_no_permission(self):
        messages.error(self.request, 'Access restricted to approved writers only.')
        return redirect('accounts:dashboard')


class AvailableOrdersView(WriterAccessMixin, ListView):
    """View for writers to browse available orders."""
    model = Order
    template_name = 'orders/writer/available.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        """Return orders that are available for this writer."""
        user = self.request.user
        
        # Get writer's profile to check availability
        writer_profile = user.writer_profile
        
        if not writer_profile.can_accept_orders:
            return Order.objects.none()
        
        # Get orders that match writer's specialization
        queryset = Order.objects.filter(
            state='paid',
            writer__isnull=True,
            deadline__gt=timezone.now(),
        ).exclude(
            Q(client=user)  # Don't show writer's own orders
        ).select_related('client')
        
        # Filter by specialization if writer has specified
        if writer_profile.specialization:
            specializations = [s.strip().lower() for s in writer_profile.specialization.split(',')]
            
            # Create Q objects for each specialization
            specialization_filters = Q()
            for spec in specializations:
                specialization_filters |= Q(subject__icontains=spec)
            
            queryset = queryset.filter(specialization_filters)
        
        # Order by deadline (closest first) and price (highest first)
        return queryset.order_by('deadline', '-price')
    
    def get_context_data(self, **kwargs):
        """Add writer availability info to context."""
        context = super().get_context_data(**kwargs)
        
        writer_profile = self.request.user.writer_profile
        
        context.update({
            'writer_profile': writer_profile,
            'can_accept_orders': writer_profile.can_accept_orders,
            'current_orders': writer_profile.current_orders,
            'max_orders': writer_profile.max_orders,
            'specialization': writer_profile.specialization,
        })
        
        return context


class OrderAssignmentView(WriterAccessMixin, DetailView):
    """View for writers to view and accept order assignments."""
    model = Order
    template_name = 'orders/writer/assignment.html'
    context_object_name = 'order'
    
    def get_queryset(self):
        """Return orders that are available for assignment."""
        return Order.objects.filter(
            state='paid',
            writer__isnull=True,
            deadline__gt=timezone.now(),
        )
    
    def dispatch(self, request, *args, **kwargs):
        """Check if writer can accept this order."""
        order = self.get_object()
        writer = request.user
        
        # Check if writer is available
        if not writer.writer_profile.can_accept_orders:
            messages.error(request, 'You are not currently available for new assignments.')
            return redirect('orders:available')
        
        # Check if order is still available
        if order.writer or order.state != 'paid':
            messages.error(request, 'This order is no longer available.')
            return redirect('orders:available')
        
        # Check if writer has required expertise
        if not self._has_required_expertise(order, writer):
            messages.warning(
                request,
                'This order may not match your specialization. '
                'Please only accept orders you are qualified to complete.'
            )
        
        return super().dispatch(request, *args, **kwargs)
    
    def _has_required_expertise(self, order, writer):
        """Check if writer has required expertise for the order."""
        if not writer.writer_profile.specialization:
            return True
        
        writer_specializations = [
            s.strip().lower() 
            for s in writer.writer_profile.specialization.split(',')
        ]
        
        order_subject = order.subject.lower()
        
        return any(
            spec in order_subject or order_subject in spec
            for spec in writer_specializations
        )
    
    def post(self, request, *args, **kwargs):
        """Handle order acceptance."""
        order = self.get_object()
        
        try:
            # Use assignment service to assign order
            AssignmentService.assign_order_to_writer(
                order_id=order.id,
                writer_id=request.user.id,
                admin_user=None,  # Self-assignment
            )
            
            messages.success(
                request,
                f'Order #{order.order_number} assigned to you successfully.'
            )
            
            return redirect('orders:writer_orders')
            
        except Exception as e:
            messages.error(request, f'Error accepting order: {str(e)}')
            return redirect('orders:assignment', pk=order.pk)


class WriterOrderListView(WriterAccessMixin, ListView):
    """View for writers to list their assigned orders."""
    model = Order
    template_name = 'orders/writer/list.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        """Return orders assigned to this writer."""
        return Order.objects.filter(
            writer=self.request.user
        ).select_related('client').order_by('deadline')
    
    def get_context_data(self, **kwargs):
        """Add writer stats and deadlines to context."""
        context = super().get_context_data(**kwargs)
        
        user = self.request.user
        now = timezone.now()
        
        # Get overdue and upcoming orders
        orders = self.get_queryset()
        
        overdue = orders.filter(deadline__lt=now).exclude(
            state__in=['completed', 'cancelled', 'refunded']
        )
        
        upcoming = orders.filter(
            deadline__gt=now,
            deadline__lte=now + timezone.timedelta(hours=24)
        ).exclude(
            state__in=['completed', 'cancelled', 'refunded']
        )
        
        context.update({
            'overdue_orders': overdue,
            'upcoming_orders': upcoming,
            'writer_profile': user.writer_profile,
            'stats': self._get_writer_stats(user),
        })
        
        return context
    
    def _get_writer_stats(self, writer):
        """Get writer order statistics."""
        orders = Order.objects.filter(writer=writer)
        
        return {
            'total_assigned': orders.count(),
            'in_progress': orders.filter(
                state__in=['assigned', 'in_progress', 'in_revision']
            ).count(),
            'completed': orders.filter(state='completed').count(),
            'overdue': orders.filter(
                deadline__lt=timezone.now()
            ).exclude(
                state__in=['completed', 'cancelled', 'refunded']
            ).count(),
            'completion_rate': (
                orders.filter(state='completed').count() / 
                max(orders.count(), 1) * 100
            ),
        }


class OrderDeliveryView(WriterAccessMixin, DetailView):
    """View for writers to deliver completed work."""
    model = Order
    template_name = 'orders/writer/delivery.html'
    context_object_name = 'order'
    
    def get_queryset(self):
        """Return orders assigned to this writer that can be delivered."""
        return Order.objects.filter(
            writer=self.request.user,
            state__in=['in_progress', 'in_revision']
        )
    
    def dispatch(self, request, *args, **kwargs):
        """Check if order can be delivered."""
        order = self.get_object()
        
        if order.state not in ['in_progress', 'in_revision']:
            messages.error(request, 'This order is not ready for delivery.')
            return redirect('orders:writer_orders')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add delivery form and checklist to context."""
        context = super().get_context_data(**kwargs)
        
        order = self.object
        
        # Get or create delivery checklist
        from apps.orders.models import DeliveryChecklist
        
        checklist, created = DeliveryChecklist.objects.get_or_create(order=order)
        
        context.update({
            'delivery_form': DeliveryForm(),
            'checklist': checklist,
            'files': order.files.filter(
                file_type__in=['instructions', 'reference']
            ),
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle order delivery."""
        order = self.get_object()
        form = DeliveryForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Use delivery service to deliver order
                DeliveryService.deliver_order(
                    order_id=order.id,
                    writer_id=request.user.id,
                    files=request.FILES.getlist('files'),
                    notes=form.cleaned_data.get('notes', ''),
                    checklist_data=form.cleaned_data.get('checklist', {})
                )
                
                messages.success(
                    request,
                    f'Order #{order.order_number} delivered successfully.'
                )
                
                return redirect('orders:writer_orders')
                
            except Exception as e:
                messages.error(request, f'Error delivering order: {str(e)}')
        
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        return self.get(request, *args, **kwargs)