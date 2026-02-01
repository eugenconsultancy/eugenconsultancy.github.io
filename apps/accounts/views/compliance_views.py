from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, FormView, ListView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect

from apps.accounts.forms.compliance_forms import DataRequestForm
from apps.compliance.models import DataRequest, ConsentLog
from apps.compliance.services import DataRequestService


class DataRequestView(LoginRequiredMixin, FormView):
    """View for submitting GDPR data requests."""
    template_name = 'accounts/compliance/data_request.html'
    form_class = DataRequestForm
    success_url = reverse_lazy('accounts:data_request')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get user's previous data requests
        previous_requests = DataRequest.objects.filter(
            user=self.request.user
        ).order_by('-received_at')[:10]
        
        context.update({
            'previous_requests': previous_requests,
            'request_service': DataRequestService(),
        })
        
        return context
    
    def form_valid(self, form):
        """Handle data request submission."""
        try:
            request_service = DataRequestService()
            
            data_request = request_service.create_data_request(
                user_id=self.request.user.id,
                request_type=form.cleaned_data['request_type'],
                description=form.cleaned_data['description']
            )
            
            messages.success(
                self.request,
                f'{data_request.get_request_type_display()} request submitted successfully. '
                f'Request ID: {data_request.request_id}'
            )
            
            # Send confirmation email (in production)
            # send_data_request_confirmation.delay(data_request.id)
            
        except Exception as e:
            messages.error(self.request, f'Error submitting request: {str(e)}')
            return self.form_invalid(form)
        
        return super().form_valid(form)


class ConsentHistoryView(LoginRequiredMixin, ListView):
    """View for viewing consent history."""
    template_name = 'accounts/compliance/consent_history.html'
    context_object_name = 'consents'
    paginate_by = 20
    
    def get_queryset(self):
        return ConsentLog.objects.filter(
            user=self.request.user
        ).select_related('user').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get consent statistics
        total_consents = self.get_queryset().count()
        active_consents = self.get_queryset().filter(consent_given=True).count()
        
        context.update({
            'total_consents': total_consents,
            'active_consents': active_consents,
            'consent_withdrawal_rate': (
                (total_consents - active_consents) / total_consents * 100
            ) if total_consents > 0 else 0,
        })
        
        return context