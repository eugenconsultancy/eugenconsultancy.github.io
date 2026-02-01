"""
Action views for order operations.
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import FormView, UpdateView, View, CreateView
from django.utils import timezone
from django.db import transaction

from apps.orders.models import Order, OrderFile
from apps.orders.forms import (
    RevisionRequestForm, DeliveryForm, 
    DisputeResolutionForm, AdminAssignmentForm,
    OrderFileForm
)
from apps.orders.services import (
    DeliveryService, DisputeService, 
    AssignmentService
)


class RevisionRequestView(LoginRequiredMixin, UpdateView):
    """View for clients to request revisions."""
    model = Order
    form_class = RevisionRequestForm
    template_name = 'orders/revision_request.html'
    
    def get_queryset(self):
        """Only allow clients to request revisions on their delivered orders."""
        return Order.objects.filter(
            client=self.request.user,
            state='delivered'
        )
    
    def get_success_url(self):
        return reverse_lazy('orders:detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        """Handle successful revision request."""
        order = form.save(commit=False)
        
        try:
            with transaction.atomic():
                # Use delivery service to request revision
                DeliveryService.request_revision(
                    order_id=order.id,
                    client_id=self.request.user.id,
                    reason=form.cleaned_data['reason'],
                    revision_details=form.cleaned_data.get('details', '')
                )
            
            messages.success(self.request, 'Revision requested successfully.')
            return redirect(self.get_success_url())
            
        except Exception as e:
            messages.error(self.request, f'Error requesting revision: {str(e)}')
            return self.form_invalid(form)


class OrderCompletionView(LoginRequiredMixin, View):
    """View for clients to complete orders."""
    
    def post(self, request, pk):
        """Mark order as completed."""
        order = get_object_or_404(Order, pk=pk, client=request.user)
        
        if order.state != 'delivered':
            messages.error(request, 'Order must be delivered before completion.')
            return redirect('orders:detail', pk=pk)
        
        try:
            with transaction.atomic():
                # Use delivery service to complete order
                DeliveryService.complete_order(
                    order_id=order.id,
                    client_id=request.user.id
                )
            
            messages.success(request, 'Order marked as completed successfully.')
            
        except Exception as e:
            messages.error(request, f'Error completing order: {str(e)}')
        
        return redirect('orders:detail', pk=pk)


class DisputeRaiseView(LoginRequiredMixin, FormView):
    """View for clients to raise disputes."""
    form_class = DisputeResolutionForm
    template_name = 'orders/dispute_raise.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Check if order can be disputed."""
        self.order = get_object_or_404(Order, pk=kwargs['pk'], client=request.user)
        
        valid_states = ['delivered', 'in_revision', 'revision_requested']
        if self.order.state not in valid_states:
            messages.error(request, 'Cannot raise dispute for order in current state.')
            return redirect('orders:detail', pk=self.order.pk)
        
        if self.order.state == 'disputed':
            messages.error(request, 'Dispute already raised for this order.')
            return redirect('orders:detail', pk=self.order.pk)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add order to context."""
        context = super().get_context_data(**kwargs)
        context['order'] = self.order
        return context
    
    def get_success_url(self):
        return reverse_lazy('orders:detail', kwargs={'pk': self.order.pk})
    
    def form_valid(self, form):
        """Handle dispute submission."""
        try:
            with transaction.atomic():
                # Use dispute service to raise dispute
                DisputeService.raise_dispute(
                    order_id=self.order.id,
                    client_id=self.request.user.id,
                    reason=form.cleaned_data['reason'],
                    details=form.cleaned_data.get('details', ''),
                    evidence_files=self.request.FILES.getlist('evidence_files')
                )
            
            messages.success(self.request, 'Dispute raised successfully.')
            
        except Exception as e:
            messages.error(self.request, f'Error raising dispute: {str(e)}')
            return self.form_invalid(form)
        
        return super().form_valid(form)


class StartWorkView(LoginRequiredMixin, View):
    """View for writers to start work on assigned orders."""
    
    def post(self, request, pk):
        """Start work on order."""
        order = get_object_or_404(Order, pk=pk, writer=request.user)
        
        if order.state != 'assigned':
            messages.error(request, 'Order must be assigned before starting work.')
            return redirect('orders:detail', pk=pk)
        
        try:
            with transaction.atomic():
                order.start_work()
                order.save()
            
            messages.success(request, 'Work started successfully.')
            
        except Exception as e:
            messages.error(request, f'Error starting work: {str(e)}')
        
        return redirect('orders:detail', pk=pk)


class AcceptRevisionView(LoginRequiredMixin, View):
    """View for writers to accept revision requests."""
    
    def post(self, request, pk):
        """Accept revision request."""
        order = get_object_or_404(Order, pk=pk, writer=request.user)
        
        if order.state != 'revision_requested':
            messages.error(request, 'No pending revision request found.')
            return redirect('orders:detail', pk=pk)
        
        try:
            with transaction.atomic():
                order.accept_revision()
                order.save()
            
            messages.success(request, 'Revision accepted successfully.')
            
        except Exception as e:
            messages.error(request, f'Error accepting revision: {str(e)}')
        
        return redirect('orders:detail', pk=pk)


class WorkSubmissionView(LoginRequiredMixin, FormView):
    """View for writers to submit work."""
    form_class = DeliveryForm
    template_name = 'orders/work_submission.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Check if order can be submitted."""
        self.order = get_object_or_404(Order, pk=kwargs['pk'], writer=request.user)
        
        valid_states = ['in_progress', 'in_revision']
        if self.order.state not in valid_states:
            messages.error(request, 'Cannot submit work for order in current state.')
            return redirect('orders:detail', pk=self.order.pk)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add order to context."""
        context = super().get_context_data(**kwargs)
        context['order'] = self.order
        return context
    
    def get_success_url(self):
        return reverse_lazy('orders:detail', kwargs={'pk': self.order.pk})
    
    def form_valid(self, form):
        """Handle work submission."""
        try:
            with transaction.atomic():
                # Use delivery service to deliver order
                DeliveryService.deliver_order(
                    order_id=self.order.id,
                    writer_id=self.request.user.id,
                    files=self.request.FILES.getlist('files'),
                    notes=form.cleaned_data.get('notes', ''),
                    checklist_data=form.cleaned_data.get('checklist', {})
                )
            
            messages.success(self.request, 'Work submitted successfully.')
            
        except Exception as e:
            messages.error(self.request, f'Error submitting work: {str(e)}')
            return self.form_invalid(form)
        
        return super().form_valid(form)


class FileUploadView(LoginRequiredMixin, CreateView):
    """View for uploading files to orders."""
    model = OrderFile
    form_class = OrderFileForm
    template_name = 'orders/file_upload.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Get order and check permissions."""
        self.order = get_object_or_404(Order, pk=kwargs['pk'])
        
        # Check if user has permission to upload files
        if not (request.user.is_staff or 
                self.order.client == request.user or 
                self.order.writer == request.user):
            messages.error(request, 'You do not have permission to upload files to this order.')
            return redirect('orders:detail', pk=self.order.pk)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add order to context."""
        context = super().get_context_data(**kwargs)
        context['order'] = self.order
        return context
    
    def get_success_url(self):
        return reverse_lazy('orders:detail', kwargs={'pk': self.order.pk})
    
    def form_valid(self, form):
        """Save file with order and user info."""
        form.instance.order = self.order
        form.instance.uploaded_by = self.request.user
        
        try:
            response = super().form_valid(form)
            messages.success(self.request, 'File uploaded successfully.')
            return response
            
        except Exception as e:
            messages.error(self.request, f'Error uploading file: {str(e)}')
            return self.form_invalid(form)


class AdminAssignView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """Admin view to assign order to writer."""
    form_class = AdminAssignmentForm
    template_name = 'orders/admin/assign.html'
    
    def test_func(self):
        return self.request.user.is_staff
    
    def dispatch(self, request, *args, **kwargs):
        """Get order and check if it can be assigned."""
        self.order = get_object_or_404(Order, pk=kwargs['pk'])
        
        if not self.order.can_be_assigned:
            messages.error(request, 'Order cannot be assigned in current state.')
            return redirect('orders:admin_detail', pk=self.order.pk)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add order to context."""
        context = super().get_context_data(**kwargs)
        context['order'] = self.order
        
        # Get available writers
        from apps.accounts.models import User
        available_writers = User.objects.filter(
            user_type='writer',
            writer_profile__is_available=True,
            verification_status__state='approved',
        ).select_related('writer_profile')
        
        context['available_writers'] = available_writers
        return context
    
    def get_initial(self):
        """Set initial form values."""
        initial = super().get_initial()
        initial['order_id'] = self.order.id
        return initial
    
    def get_success_url(self):
        return reverse_lazy('orders:admin_detail', kwargs={'pk': self.order.pk})
    
    def form_valid(self, form):
        """Handle order assignment."""
        try:
            with transaction.atomic():
                # Use assignment service to assign order
                AssignmentService.assign_order_to_writer(
                    order_id=form.cleaned_data['order_id'],
                    writer_id=form.cleaned_data['writer_id'],
                    admin_user=self.request.user,
                    notes=form.cleaned_data.get('assignment_notes', '')
                )
            
            messages.success(self.request, 'Order assigned successfully.')
            
        except Exception as e:
            messages.error(self.request, f'Error assigning order: {str(e)}')
            return self.form_invalid(form)
        
        return super().form_valid(form)


class AdminCancelView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Admin view to cancel orders."""
    
    def test_func(self):
        return self.request.user.is_staff
    
    def post(self, request, pk):
        """Cancel order."""
        order = get_object_or_404(Order, pk=pk)
        
        valid_states = ['paid', 'assigned', 'in_progress']
        if order.state not in valid_states:
            messages.error(request, 'Order cannot be cancelled in current state.')
            return redirect('orders:admin_detail', pk=order.pk)
        
        try:
            with transaction.atomic():
                order.cancel(reason=request.POST.get('reason', 'Cancelled by admin'))
                order.save()
            
            messages.success(request, 'Order cancelled successfully.')
            
        except Exception as e:
            messages.error(request, f'Error cancelling order: {str(e)}')
        
        return redirect('orders:admin_detail', pk=order.pk)


class ForceCompleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Admin view to force complete orders."""
    
    def test_func(self):
        return self.request.user.is_staff
    
    def post(self, request, pk):
        """Force complete order."""
        order = get_object_or_404(Order, pk=pk)
        
        valid_states = ['delivered', 'revision_requested', 'in_revision']
        if order.state not in valid_states:
            messages.error(request, 'Order cannot be force completed in current state.')
            return redirect('orders:admin_detail', pk=order.pk)
        
        try:
            with transaction.atomic():
                order.state = 'completed'
                order.completed_at = timezone.now()
                order.save()
                
                # Release payment to writer
                if hasattr(order, '_release_writer_payment'):
                    order._release_writer_payment()
            
            messages.success(request, 'Order force completed successfully.')
            
        except Exception as e:
            messages.error(request, f'Error force completing order: {str(e)}')
        
        return redirect('orders:admin_detail', pk=order.pk)


class AdminRefundView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Admin view to refund orders."""
    
    def test_func(self):
        return self.request.user.is_staff
    
    def post(self, request, pk):
        """Process refund."""
        order = get_object_or_404(Order, pk=pk)
        
        try:
            amount = float(request.POST.get('amount', 0))
            if amount <= 0 or amount > order.price:
                messages.error(request, 'Invalid refund amount.')
                return redirect('orders:admin_detail', pk=order.pk)
            
            with transaction.atomic():
                # Use dispute service for refund
                from apps.orders.services.dispute_trigger import DisputeService
                
                if amount == order.price:
                    DisputeService._process_full_refund(order, request.user, 'Admin refund')
                else:
                    DisputeService._process_partial_refund(order, request.user, amount, 'Admin refund')
                
                order.save()
            
            messages.success(request, f'Refund of ${amount} processed successfully.')
            
        except Exception as e:
            messages.error(request, f'Error processing refund: {str(e)}')
        
        return redirect('orders:admin_detail', pk=order.pk)


class AdminReassignView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Admin view to reassign orders to different writers."""
    
    def test_func(self):
        return self.request.user.is_staff
    
    def post(self, request, pk):
        """Reassign order to different writer."""
        order = get_object_or_404(Order, pk=pk)
        writer_id = request.POST.get('writer_id')
        
        if not writer_id:
            messages.error(request, 'Writer ID is required.')
            return redirect('orders:admin_detail', pk=order.pk)
        
        valid_states = ['assigned', 'in_progress', 'in_revision']
        if order.state not in valid_states:
            messages.error(request, 'Order cannot be reassigned in current state.')
            return redirect('orders:admin_detail', pk=order.pk)
        
        try:
            with transaction.atomic():
                # Get current writer
                old_writer = order.writer
                
                # Get new writer
                from apps.accounts.models import User
                new_writer = User.objects.get(
                    id=writer_id,
                    user_type='writer',
                    writer_profile__is_available=True,
                    verification_status__state='approved',
                )
                
                # Update order
                order.writer = new_writer
                order.save()
                
                # Update writer profiles
                if old_writer:
                    old_writer.writer_profile.current_orders = max(
                        0, old_writer.writer_profile.current_orders - 1
                    )
                    old_writer.writer_profile.save()
                
                new_writer.writer_profile.current_orders += 1
                new_writer.writer_profile.save()
                
                # Send notifications
                from apps.notifications.tasks import send_order_notification
                send_order_notification.delay(
                    user_id=new_writer.id,
                    order_id=order.id,
                    notification_type='order_reassigned',
                    assigned_by=request.user.get_full_name(),
                    deadline=order.deadline.isoformat(),
                )
                
                if old_writer:
                    send_order_notification.delay(
                        user_id=old_writer.id,
                        order_id=order.id,
                        notification_type='order_unassigned',
                        reassigned_to=new_writer.get_full_name(),
                    )
            
            messages.success(request, 'Order reassigned successfully.')
            
        except Exception as e:
            messages.error(request, f'Error reassigning order: {str(e)}')
        
        return redirect('orders:admin_detail', pk=order.pk)