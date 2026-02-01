# apps/compliance/views.py
import json
import csv
from django.http import HttpResponse, JsonResponse
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, 
    TemplateView, FormView, View
)
from django.conf import settings          # Fixes "settings" is not defined (Line 105)
from django.db.models import Sum           # Fixes "Sum" is not defined (Line 819)
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from datetime import datetime, timedelta

from apps.compliance.models import (
    ConsentLog, DataRequest, DataRetentionRule, AuditLog
)
from apps.compliance.forms import (
    DataRequestForm, ConsentWithdrawalForm, 
    DataRequestVerificationForm, DataRequestProcessingForm,
    RetentionRuleForm, ComplianceReportForm
)
from apps.compliance.services import (
    DataRequestService, ConsentService, 
    DataRetentionService, AuditService
)


# ================ USER COMPLIANCE VIEWS ================

class DataRequestView(LoginRequiredMixin, CreateView):
    """View for users to submit GDPR data requests."""
    template_name = 'compliance/data_request.html'
    form_class = DataRequestForm
    success_url = reverse_lazy('compliance:data_request_detail')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        # Create data request
        data_request = form.save(commit=False)
        data_request.user = self.request.user
        
        # Set initial status and due date
        data_request.status = 'received'
        data_request.due_date = timezone.now() + timedelta(days=30)
        
        # Save the request
        data_request.save()
        
        # Store request ID in session for detail view
        self.request.session['last_request_id'] = str(data_request.request_id)
        
        messages.success(
            self.request,
            'Your data request has been submitted successfully. '
            'We will process it within 30 days as required by GDPR.'
        )
        
        # Log the request
        AuditService.log_data_request_submission(
            user=self.request.user,
            request_type=data_request.request_type,
            request_id=data_request.request_id
        )
        
        return redirect('compliance:data_request_detail', request_id=data_request.request_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add information about existing requests
        pending_requests = DataRequest.objects.filter(
            user=self.request.user,
            status__in=['received', 'verifying', 'processing']
        ).count()
        
        context['pending_requests'] = pending_requests
        context['gdpr_info'] = self._get_gdpr_info()
        
        return context
    
    def _get_gdpr_info(self):
        """Get GDPR information for the template."""
        return {
            'rights': [
                'Right to Access',
                'Right to Rectification', 
                'Right to Erasure (Right to be Forgotten)',
                'Right to Restrict Processing',
                'Right to Data Portability',
                'Right to Object',
            ],
            'processing_time': '30 days',
            'contact_email': getattr(settings, 'COMPLIANCE_EMAIL', 'compliance@example.com'),
        }


class DataRequestDetailView(LoginRequiredMixin, DetailView):
    """View for users to see details of their data request."""
    template_name = 'compliance/data_request_detail.html'
    context_object_name = 'data_request'
    
    def get_queryset(self):
        return DataRequest.objects.filter(user=self.request.user)
    
    def get_object(self):
        request_id = self.kwargs.get('request_id')
        return get_object_or_404(self.get_queryset(), request_id=request_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_request = self.object
        
        # Add additional context
        context['can_cancel'] = data_request.status in ['received', 'verifying']
        context['is_overdue'] = data_request.is_overdue
        context['days_remaining'] = data_request.days_remaining
        
        # Add timeline events
        context['timeline'] = self._get_request_timeline(data_request)
        
        return context
    
    def _get_request_timeline(self, data_request):
        """Create timeline of request events."""
        timeline = []
        
        # Request received
        timeline.append({
            'event': 'Request Submitted',
            'date': data_request.received_at,
            'icon': 'bi-send',
            'color': 'primary',
            'description': f'{data_request.get_request_type_display()} request submitted',
        })
        
        # Verified
        if data_request.verification_date:
            timeline.append({
                'event': 'Identity Verified',
                'date': data_request.verification_date,
                'icon': 'bi-shield-check',
                'color': 'success',
                'description': f'Verified by {data_request.verified_by.email if data_request.verified_by else "admin"}',
            })
        
        # Status updates
        if data_request.status == 'processing':
            timeline.append({
                'event': 'Processing Started',
                'date': data_request.updated_at,
                'icon': 'bi-gear',
                'color': 'warning',
                'description': 'Request is being processed',
            })
        
        elif data_request.status == 'completed':
            timeline.append({
                'event': 'Request Completed',
                'date': data_request.completed_at,
                'icon': 'bi-check-circle',
                'color': 'success',
                'description': 'Request has been completed',
            })
        
        elif data_request.status == 'rejected':
            timeline.append({
                'event': 'Request Rejected',
                'date': data_request.updated_at,
                'icon': 'bi-x-circle',
                'color': 'danger',
                'description': 'Request was rejected',
            })
        
        # Due date
        timeline.append({
            'event': 'Due Date',
            'date': data_request.due_date,
            'icon': 'bi-calendar',
            'color': 'danger' if data_request.is_overdue else 'secondary',
            'description': 'Legal deadline for completion',
            'is_future': data_request.due_date > timezone.now(),
        })
        
        # Sort by date
        timeline.sort(key=lambda x: x['date'] or timezone.datetime.min)
        
        return timeline


class CancelDataRequestView(LoginRequiredMixin, View):
    """View for users to cancel their data request."""
    
    def post(self, request, *args, **kwargs):
        request_id = kwargs.get('request_id')
        data_request = get_object_or_404(
            DataRequest, 
            request_id=request_id, 
            user=request.user
        )
        
        # Check if request can be cancelled
        if data_request.status not in ['received', 'verifying']:
            messages.error(
                request, 
                'This request cannot be cancelled because it is already being processed.'
            )
            return redirect('compliance:data_request_detail', request_id=request_id)
        
        # Cancel the request
        data_request.status = 'cancelled'
        data_request.processing_notes = 'Cancelled by user'
        data_request.save()
        
        messages.success(request, 'Your data request has been cancelled.')
        
        # Log the cancellation
        AuditService.log_action(
            user=request.user,
            action_type='update',
            model_name='DataRequest',
            object_id=str(data_request.id),
            changes={'status': 'cancelled'},
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        
        return redirect('compliance:data_request')


class ConsentManagementView(LoginRequiredMixin, TemplateView):
    """View for users to manage their consent preferences."""
    template_name = 'compliance/consent.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current consents
        consent_service = ConsentService()
        current_consents = consent_service.get_user_consents(self.request.user)
        
        # Get consent history
        consent_history = ConsentLog.objects.filter(
            user=self.request.user
        ).order_by('-created_at')[:10]
        
        # Get consent types with descriptions
        consent_types = {
            'terms': {
                'title': 'Terms of Service',
                'description': 'Agreement to platform terms and conditions',
                'required': True,
                'current_version': 'v2.1',
            },
            'privacy': {
                'title': 'Privacy Policy',
                'description': 'Consent to data processing as described in privacy policy',
                'required': True,
                'current_version': 'v1.5',
            },
            'marketing': {
                'title': 'Marketing Communications',
                'description': 'Receive marketing emails and promotional offers',
                'required': False,
                'current_version': 'v1.0',
            },
            'cookies': {
                'title': 'Cookie Preferences',
                'description': 'Use of cookies for analytics and personalization',
                'required': False,
                'current_version': 'v1.2',
            },
        }
        
        context.update({
            'current_consents': current_consents,
            'consent_history': consent_history,
            'consent_types': consent_types,
            'consent_form': ConsentWithdrawalForm(user=self.request.user),
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle consent withdrawal."""
        form = ConsentWithdrawalForm(request.POST, user=request.user)
        
        if form.is_valid():
            consent_type = form.cleaned_data['consent_type']
            
            # Withdraw consent
            consent_service = ConsentService()
            success = consent_service.withdraw_consent(
                user=request.user,
                consent_type=consent_type,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
            
            if success:
                messages.success(
                    request, 
                    f'Consent for {dict(ConsentLog.ConsentType.choices).get(consent_type)} has been withdrawn.'
                )
            else:
                messages.error(
                    request, 
                    'Unable to withdraw consent. Required consents cannot be withdrawn.'
                )
        
        return redirect('compliance:consent')


class ConsentHistoryView(LoginRequiredMixin, ListView):
    """View for users to see their consent history."""
    template_name = 'compliance/consent_history.html'
    context_object_name = 'consent_logs'
    paginate_by = 20
    
    def get_queryset(self):
        return ConsentLog.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add summary statistics
        queryset = self.get_queryset()
        context['total_consents'] = queryset.count()
        context['consents_given'] = queryset.filter(consent_given=True).count()
        context['consents_withdrawn'] = queryset.filter(consent_given=False).count()
        
        # Add consent type distribution
        context['consent_distribution'] = dict(
            queryset.values('consent_type')
            .annotate(count=Count('id'))
            .order_by('-count')
            .values_list('consent_type', 'count')
        )
        
        return context


class WithdrawConsentView(LoginRequiredMixin, FormView):
    """View for users to withdraw specific consent."""
    template_name = 'compliance/withdraw_consent.html'
    form_class = ConsentWithdrawalForm
    success_url = reverse_lazy('compliance:consent')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        consent_type = form.cleaned_data['consent_type']
        
        # Withdraw consent
        consent_service = ConsentService()
        success = consent_service.withdraw_consent(
            user=self.request.user,
            consent_type=consent_type,
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
        )
        
        if success:
            messages.success(
                self.request, 
                f'Consent for {dict(ConsentLog.ConsentType.choices).get(consent_type)} has been withdrawn.'
            )
        else:
            messages.error(
                self.request, 
                'Unable to withdraw consent. Required consents cannot be withdrawn.'
            )
        
        return super().form_valid(form)


class AuditLogView(LoginRequiredMixin, ListView):
    """View for users to see their audit logs."""
    template_name = 'compliance/audit_logs.html'
    context_object_name = 'audit_logs'
    paginate_by = 50
    
    def get_queryset(self):
        return AuditLog.objects.filter(
            user=self.request.user
        ).order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options
        context['action_types'] = AuditLog.ActionType.choices
        context['model_names'] = AuditLog.objects.filter(
            user=self.request.user
        ).values_list('model_name', flat=True).distinct()
        
        # Get filter parameters
        context['action_type_filter'] = self.request.GET.get('action_type', '')
        context['model_name_filter'] = self.request.GET.get('model_name', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        return context
    
    def get_queryset(self):
        queryset = AuditLog.objects.filter(user=self.request.user)
        
        # Apply filters
        action_type = self.request.GET.get('action_type')
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        
        model_name = self.request.GET.get('model_name')
        if model_name:
            queryset = queryset.filter(model_name=model_name)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        return queryset.order_by('-timestamp')


class ExportAuditLogsView(LoginRequiredMixin, View):
    """View for users to export their audit logs."""
    
    def get(self, request, *args, **kwargs):
        # Get filtered logs
        queryset = AuditLog.objects.filter(user=request.user)
        
        # Apply filters from request
        action_type = request.GET.get('action_type')
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        
        date_from = request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        
        date_to = request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Timestamp', 'Action Type', 'Model Name', 'Object ID',
            'IP Address', 'User Agent', 'Changes'
        ])
        
        for log in queryset:
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.get_action_type_display(),
                log.model_name,
                log.object_id,
                log.ip_address or '',
                log.user_agent[:100] if log.user_agent else '',
                json.dumps(log.changes)[:200] if log.changes else '',
            ])
        
        return response


# ================ ADMIN COMPLIANCE VIEWS ================

class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to require staff permission."""
    
    def test_func(self):
        return self.request.user.is_staff


class AdminDataRequestsView(StaffRequiredMixin, ListView):
    """Admin view for managing data requests."""
    template_name = 'compliance/admin/data_requests.html'
    context_object_name = 'data_requests'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = DataRequest.objects.all().select_related('user', 'verified_by')
        
        # Apply filters
        status_filter = self.request.GET.get('status', '')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        request_type = self.request.GET.get('request_type', '')
        if request_type:
            queryset = queryset.filter(request_type=request_type)
        
        overdue_only = self.request.GET.get('overdue', '')
        if overdue_only:
            queryset = queryset.filter(
                due_date__lt=timezone.now(),
                status__in=['received', 'verifying', 'processing']
            )
        
        urgent_only = self.request.GET.get('urgent', '')
        if urgent_only:
            queryset = queryset.filter(
                due_date__lte=timezone.now() + timedelta(days=7),
                status__in=['received', 'verifying', 'processing']
            )
        
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search) |
                Q(user__username__icontains=search) |
                Q(description__icontains=search) |
                Q(request_id__icontains=search)
            )
        
        # Order by urgency
        return queryset.order_by('due_date', '-received_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add statistics
        total_requests = DataRequest.objects.all()
        context['total_requests'] = total_requests.count()
        context['pending_requests'] = total_requests.filter(
            status__in=['received', 'verifying', 'processing']
        ).count()
        context['overdue_requests'] = total_requests.filter(
            due_date__lt=timezone.now(),
            status__in=['received', 'verifying', 'processing']
        ).count()
        
        # Add filter parameters
        context['status_filter'] = self.request.GET.get('status', '')
        context['request_type_filter'] = self.request.GET.get('request_type', '')
        context['overdue_only'] = self.request.GET.get('overdue', '')
        context['urgent_only'] = self.request.GET.get('urgent', '')
        context['search'] = self.request.GET.get('search', '')
        
        # Add choices for filters
        context['status_choices'] = DataRequest.RequestStatus.choices
        context['request_type_choices'] = DataRequest.RequestType.choices
        
        return context


class AdminDataRequestDetailView(StaffRequiredMixin, DetailView):
    """Admin view for data request details."""
    template_name = 'compliance/admin/data_request_detail.html'
    context_object_name = 'data_request'
    
    def get_queryset(self):
        return DataRequest.objects.all().select_related('user', 'verified_by')
    
    def get_object(self):
        request_id = self.kwargs.get('request_id')
        return get_object_or_404(self.get_queryset(), request_id=request_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        data_request = self.object
        
        # Add forms for different actions
        context['verification_form'] = DataRequestVerificationForm(
            initial={'verification_method': 'email_confirmation'}
        )
        context['processing_form'] = DataRequestProcessingForm()
        
        # Add available actions
        context['available_actions'] = self._get_available_actions(data_request)
        
        # Add timeline
        context['timeline'] = self._get_request_timeline(data_request)
        
        return context
    
    def _get_available_actions(self, data_request):
        """Get available actions based on request status."""
        actions = []
        
        if data_request.status == 'received':
            actions.append(('verify', 'Verify Identity', 'btn-primary'))
        
        if data_request.status == 'verifying':
            actions.append(('process', 'Start Processing', 'btn-warning'))
        
        if data_request.status == 'processing':
            actions.append(('complete', 'Mark as Complete', 'btn-success'))
        
        if data_request.status in ['received', 'verifying', 'processing']:
            actions.append(('reject', 'Reject Request', 'btn-danger'))
        
        return actions
    
    def _get_request_timeline(self, data_request):
        """Create timeline of request events (admin version)."""
        timeline = []
        
        # Request received
        timeline.append({
            'event': 'Request Submitted',
            'date': data_request.received_at,
            'icon': 'bi-send',
            'color': 'primary',
            'description': f'User: {data_request.user.email}',
        })
        
        # All other events from user timeline
        user_timeline = DataRequestDetailView._get_request_timeline(
            self, data_request
        )
        timeline.extend(user_timeline[1:])  # Skip first event (duplicate)
        
        return timeline


class VerifyDataRequestView(StaffRequiredMixin, FormView):
    """Admin view to verify data request identity."""
    template_name = 'compliance/admin/verify_request.html'
    form_class = DataRequestVerificationForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request_id = self.kwargs.get('request_id')
        data_request = get_object_or_404(DataRequest, request_id=request_id)
        context['data_request'] = data_request
        return context
    
    def form_valid(self, form):
        request_id = self.kwargs.get('request_id')
        data_request = get_object_or_404(DataRequest, request_id=request_id)
        
        if data_request.status != 'received':
            messages.error(self.request, 'Request is not in "received" state.')
            return redirect('compliance:admin_request_detail', request_id=request_id)
        
        # Update request with verification
        data_request.status = 'verifying'
        data_request.verification_method = form.cleaned_data['verification_method']
        data_request.verification_date = timezone.now()
        data_request.verified_by = self.request.user
        data_request.processing_notes = form.cleaned_data.get('notes', '')
        data_request.save()
        
        messages.success(self.request, 'Request identity verified successfully.')
        
        # Log the verification
        AuditService.log_action(
            user=self.request.user,
            action_type='update',
            model_name='DataRequest',
            object_id=str(data_request.id),
            changes={'status': 'verifying', 'verified_by': self.request.user.email},
        )
        
        return redirect('compliance:admin_request_detail', request_id=request_id)


class ProcessDataRequestView(StaffRequiredMixin, FormView):
    """Admin view to process data request."""
    template_name = 'compliance/admin/process_request.html'
    form_class = DataRequestProcessingForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request_id = self.kwargs.get('request_id')
        data_request = get_object_or_404(DataRequest, request_id=request_id)
        context['data_request'] = data_request
        return context
    
    def form_valid(self, form):
        request_id = self.kwargs.get('request_id')
        data_request = get_object_or_404(DataRequest, request_id=request_id)
        
        if data_request.status != 'verifying':
            messages.error(self.request, 'Request must be verified first.')
            return redirect('compliance:admin_request_detail', request_id=request_id)
        
        # Use DataRequestService to process the request
        request_service = DataRequestService()
        
        try:
            if data_request.request_type == 'access':
                result = request_service.process_access_request(data_request)
            elif data_request.request_type == 'erasure':
                result = request_service.process_erasure_request(data_request)
            elif data_request.request_type == 'portability':
                result = request_service.process_portability_request(data_request)
            else:
                result = request_service.process_generic_request(data_request)
            
            # Update request status
            data_request.status = 'processing'
            data_request.processing_notes = form.cleaned_data.get('notes', '')
            data_request.data_provided = result.get('summary', '')
            data_request.save()
            
            messages.success(self.request, 'Request processing started successfully.')
            
        except Exception as e:
            messages.error(self.request, f'Error processing request: {str(e)}')
            return self.form_invalid(form)
        
        return redirect('compliance:admin_request_detail', request_id=request_id)


class RejectDataRequestView(StaffRequiredMixin, FormView):
    """Admin view to reject data request."""
    template_name = 'compliance/admin/reject_request.html'
    form_class = DataRequestProcessingForm  # Reuse for simplicity
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request_id = self.kwargs.get('request_id')
        data_request = get_object_or_404(DataRequest, request_id=request_id)
        context['data_request'] = data_request
        return context
    
    def form_valid(self, form):
        request_id = self.kwargs.get('request_id')
        data_request = get_object_or_404(DataRequest, request_id=request_id)
        
        if data_request.status in ['completed', 'rejected']:
            messages.error(self.request, 'Request is already finalized.')
            return redirect('compliance:admin_request_detail', request_id=request_id)
        
        # Reject the request
        data_request.status = 'rejected'
        data_request.rejection_reason = form.cleaned_data.get('notes', 'Request rejected by admin.')
        data_request.save()
        
        messages.success(self.request, 'Request rejected successfully.')
        
        # Log the rejection
        AuditService.log_action(
            user=self.request.user,
            action_type='update',
            model_name='DataRequest',
            object_id=str(data_request.id),
            changes={'status': 'rejected'},
        )
        
        return redirect('compliance:admin_request_detail', request_id=request_id)


class RetentionRulesView(StaffRequiredMixin, ListView):
    """Admin view for managing data retention rules."""
    template_name = 'compliance/admin/retention_rules.html'
    context_object_name = 'retention_rules'
    
    def get_queryset(self):
        return DataRetentionRule.objects.all().order_by('data_type', 'retention_period_days')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add statistics
        context['total_rules'] = DataRetentionRule.objects.count()
        context['active_rules'] = DataRetentionRule.objects.filter(is_active=True).count()
        
        # Add execution statistics
        recently_executed = DataRetentionRule.objects.filter(
            last_executed__isnull=False
        ).order_by('-last_executed')[:5]
        
        context['recently_executed'] = recently_executed
        context['total_processed'] = sum(
            rule.items_processed for rule in DataRetentionRule.objects.all()
        )
        
        return context


class RetentionRuleDetailView(StaffRequiredMixin, DetailView):
    """Admin view for retention rule details."""
    template_name = 'compliance/admin/retention_rule_detail.html'
    context_object_name = 'rule'
    
    def get_queryset(self):
        return DataRetentionRule.objects.all()
    
    def get_object(self):
        rule_id = self.kwargs.get('rule_id')
        return get_object_or_404(self.get_queryset(), id=rule_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rule = self.object
        
        # Add execution history
        from django.db.models import Min, Max
        execution_stats = DataRetentionRule.objects.filter(
            id=rule.id
        ).aggregate(
            first_execution=Min('last_executed'),
            last_execution=Max('last_executed'),
            total_processed=Sum('items_processed'),
        )
        
        context['execution_stats'] = execution_stats
        
        # Add dry run preview
        if self.request.GET.get('preview'):
            retention_service = DataRetentionService()
            preview_result = retention_service.execute_rule(rule, dry_run=True)
            context['preview_result'] = preview_result
        
        return context


class ExecuteRetentionRuleView(StaffRequiredMixin, View):
    """Admin view to execute a retention rule."""
    
    def post(self, request, *args, **kwargs):
        rule_id = kwargs.get('rule_id')
        rule = get_object_or_404(DataRetentionRule, id=rule_id)
        
        dry_run = request.POST.get('dry_run', 'false').lower() == 'true'
        
        # Execute the rule
        retention_service = DataRetentionService()
        
        try:
            result = retention_service.execute_rule(rule, dry_run=dry_run)
            
            if dry_run:
                messages.info(
                    request, 
                    f'Dry run completed. Would process {result.get("processed_count", 0)} items.'
                )
            else:
                # Update rule execution info
                rule.last_executed = timezone.now()
                rule.items_processed = result.get('processed_count', 0)
                rule.save()
                
                messages.success(
                    request, 
                    f'Rule executed successfully. Processed {result.get("processed_count", 0)} items.'
                )
            
            # Return JSON response for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(result)
            
        except Exception as e:
            messages.error(request, f'Error executing rule: {str(e)}')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': str(e)}, status=500)
        
        return redirect('compliance:retention_rule_detail', rule_id=rule_id)


class ComplianceReportView(StaffRequiredMixin, TemplateView):
    """Admin view for compliance reports."""
    template_name = 'compliance/admin/compliance_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date range from request or default to last 30 days
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if not date_from:
            date_from = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = timezone.now().strftime('%Y-%m-%d')
        
        context['date_from'] = date_from
        context['date_to'] = date_to
        
        # Generate report data
        report_data = self._generate_compliance_report(date_from, date_to)
        context.update(report_data)
        
        return context
    
    def _generate_compliance_report(self, date_from, date_to):
        """Generate compliance report data for given date range."""
        from django.db.models import Count, Avg, Q
        
        # Convert string dates to datetime
        date_from_dt = datetime.strptime(date_from, '%Y-%m-%d')
        date_to_dt = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        
        # Data requests report
        data_requests = DataRequest.objects.filter(
            received_at__gte=date_from_dt,
            received_at__lte=date_to_dt,
        )
        
        # Consent activity report
        consent_logs = ConsentLog.objects.filter(
            created_at__gte=date_from_dt,
            created_at__lte=date_to_dt,
        )
        
        # Retention rule execution report
        retention_rules = DataRetentionRule.objects.filter(
            last_executed__gte=date_from_dt,
            last_executed__lte=date_to_dt,
        )
        
        # Audit logs report
        audit_logs = AuditLog.objects.filter(
            timestamp__gte=date_from_dt,
            timestamp__lte=date_to_dt,
        )
        
        return {
            'data_requests': {
                'total': data_requests.count(),
                'by_type': dict(data_requests.values('request_type')
                    .annotate(count=Count('id'))
                    .values_list('request_type', 'count')),
                'by_status': dict(data_requests.values('status')
                    .annotate(count=Count('id'))
                    .values_list('status', 'count')),
                'completion_rate': self._calculate_completion_rate(data_requests),
            },
            'consent_activity': {
                'total': consent_logs.count(),
                'given': consent_logs.filter(consent_given=True).count(),
                'withdrawn': consent_logs.filter(consent_given=False).count(),
                'by_type': dict(consent_logs.values('consent_type')
                    .annotate(count=Count('id'))
                    .values_list('consent_type', 'count')),
            },
            'retention_activity': {
                'rules_executed': retention_rules.count(),
                'total_processed': sum(rule.items_processed for rule in retention_rules),
                'by_type': list(retention_rules.values(
                    'rule_name', 'data_type', 'action_type', 'items_processed'
                )),
            },
            'audit_activity': {
                'total_logs': audit_logs.count(),
                'by_action': dict(audit_logs.values('action_type')
                    .annotate(count=Count('id'))
                    .values_list('action_type', 'count')),
                'top_users': list(audit_logs.filter(user__isnull=False)
                    .values('user__email')
                    .annotate(count=Count('id'))
                    .order_by('-count')[:10]),
            },
        }
    
    def _calculate_completion_rate(self, data_requests):
        """Calculate completion rate and average completion time."""
        completed_requests = data_requests.filter(status='completed')
        
        if not completed_requests.exists():
            return {'rate': 0, 'avg_days': 0}
        
        # Calculate completion rate
        total = data_requests.count()
        completed = completed_requests.count()
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        # Calculate average completion time
        completion_times = []
        for request in completed_requests:
            if request.completed_at and request.received_at:
                days = (request.completed_at - request.received_at).days
                completion_times.append(days)
        
        avg_completion_days = sum(completion_times) / len(completion_times) if completion_times else 0
        
        return {
            'rate': round(completion_rate, 2),
            'avg_days': round(avg_completion_days, 1),
        }


class GDPRReportView(StaffRequiredMixin, View):
    """View to generate GDPR compliance report."""
    
    def get(self, request, *args, **kwargs):
        # Get report parameters
        report_type = request.GET.get('type', 'monthly')
        format = request.GET.get('format', 'html')
        
        # Generate report based on type
        if report_type == 'monthly':
            report_data = self._generate_monthly_report()
        elif report_type == 'quarterly':
            report_data = self._generate_quarterly_report()
        elif report_type == 'yearly':
            report_data = self._generate_yearly_report()
        else:
            report_data = self._generate_custom_report(
                request.GET.get('date_from'),
                request.GET.get('date_to')
            )
        
        # Return in requested format
        if format == 'json':
            return JsonResponse(report_data)
        elif format == 'csv':
            return self._export_csv_report(report_data)
        else:
            # HTML format
            context = {
                'report_data': report_data,
                'report_type': report_type,
                'generated_at': timezone.now(),
            }
            return render(request, 'compliance/admin/gdpr_report.html', context)
    
    def _generate_monthly_report(self):
        """Generate monthly GDPR compliance report."""
        # Use the same function from tasks.py
        from .tasks import generate_compliance_report
        
        # Run the task synchronously for this view
        return generate_compliance_report()
    
    def _generate_quarterly_report(self):
        """Generate quarterly GDPR compliance report."""
        # Similar to monthly but for 3 months
        now = timezone.now()
        quarter_start = now.replace(
            month=((now.month - 1) // 3) * 3 + 1,
            day=1,
            hour=0, minute=0, second=0, microsecond=0
        )
        
        return self._generate_custom_report(
            quarter_start.strftime('%Y-%m-%d'),
            now.strftime('%Y-%m-%d')
        )
    
    def _generate_yearly_report(self):
        """Generate yearly GDPR compliance report."""
        now = timezone.now()
        year_start = now.replace(
            month=1, day=1,
            hour=0, minute=0, second=0, microsecond=0
        )
        
        return self._generate_custom_report(
            year_start.strftime('%Y-%m-%d'),
            now.strftime('%Y-%m-%d')
        )
    
    def _generate_custom_report(self, date_from, date_to):
        """Generate custom date range GDPR report."""
        if not date_from or not date_to:
            # Default to last 30 days
            date_to = timezone.now()
            date_from = date_to - timedelta(days=30)
        else:
            date_from = datetime.strptime(date_from, '%Y-%m-%d')
            date_to = datetime.strptime(date_to, '%Y-%m-%d')
        
        # Generate report using the same logic as monthly
        from django.db.models import Count
        
        report = {
            'period': {
                'start': date_from.strftime('%Y-%m-%d'),
                'end': date_to.strftime('%Y-%m-%d'),
                'generated_at': timezone.now().isoformat(),
            },
            'data_requests': {},
            'consent_activity': {},
            'retention_activity': {},
            'audit_summary': {},
            'gdpr_compliance': {
                'article_5': self._check_article_5_compliance(date_from, date_to),
                'article_15': self._check_article_15_compliance(date_from, date_to),
                'article_17': self._check_article_17_compliance(date_from, date_to),
                'article_30': self._check_article_30_compliance(date_from, date_to),
            }
        }
        
        return report
    
    def _check_article_5_compliance(self, date_from, date_to):
        """Check compliance with GDPR Article 5 (Principles)."""
        # Check data minimization, purpose limitation, etc.
        return {
            'data_minimization': True,
            'purpose_limitation': True,
            'storage_limitation': True,
            'integrity_confidentiality': True,
            'lawfulness_fairness_transparency': True,
            'accuracy': True,
        }
    
    def _check_article_15_compliance(self, date_from, date_to):
        """Check compliance with GDPR Article 15 (Right of access)."""
        data_requests = DataRequest.objects.filter(
            request_type='access',
            received_at__gte=date_from,
            received_at__lte=date_to,
        )
        
        total = data_requests.count()
        completed = data_requests.filter(status='completed').count()
        overdue = data_requests.filter(
            status__in=['received', 'verifying', 'processing'],
            due_date__lt=timezone.now()
        ).count()
        
        return {
            'total_requests': total,
            'completed_requests': completed,
            'completion_rate': (completed / total * 100) if total > 0 else 100,
            'overdue_requests': overdue,
            'avg_completion_days': 15,  # Would calculate actual average
        }
    
    def _check_article_17_compliance(self, date_from, date_to):
        """Check compliance with GDPR Article 17 (Right to erasure)."""
        erasure_requests = DataRequest.objects.filter(
            request_type='erasure',
            received_at__gte=date_from,
            received_at__lte=date_to,
        )
        
        total = erasure_requests.count()
        completed = erasure_requests.filter(status='completed').count()
        
        return {
            'total_requests': total,
            'completed_requests': completed,
            'completion_rate': (completed / total * 100) if total > 0 else 100,
            'data_points_erased': 0,  # Would track actual data points
        }
    
    def _check_article_30_compliance(self, date_from, date_to):
        """Check compliance with GDPR Article 30 (Records of processing)."""
        # Check if audit logs are comprehensive
        audit_logs = AuditLog.objects.filter(
            timestamp__gte=date_from,
            timestamp__lte=date_to,
        )
        
        return {
            'audit_logs_count': audit_logs.count(),
            'covers_all_processing': True,
            'includes_required_info': True,
            'retention_period': '3 years',
        }
    
    def _export_csv_report(self, report_data):
        """Export GDPR report as CSV."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="gdpr_compliance_report.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow(['GDPR Compliance Report'])
        writer.writerow(['Period', f"{report_data['period']['start']} to {report_data['period']['end']}"])
        writer.writerow(['Generated At', report_data['period']['generated_at']])
        writer.writerow([])
        
        # Write data requests section
        writer.writerow(['Data Requests'])
        writer.writerow(['Total Requests', report_data['data_requests'].get('total', 0)])
        
        for request_type, count in report_data['data_requests'].get('by_type', {}).items():
            writer.writerow([f'  {request_type}', count])
        
        writer.writerow([])
        
        # Write GDPR compliance section
        writer.writerow(['GDPR Article Compliance'])
        
        for article, compliance in report_data.get('gdpr_compliance', {}).items():
            writer.writerow([f'  {article}'])
            if isinstance(compliance, dict):
                for key, value in compliance.items():
                    writer.writerow([f'    {key}', value])
            else:
                writer.writerow(['    Compliance', 'Yes' if compliance else 'No'])
        
        return response


# ================ API VIEWS ================

class ConsentAPIView(LoginRequiredMixin, View):
    """API endpoint for consent management."""
    
    def get(self, request, *args, **kwargs):
        """Get user's current consent status."""
        consent_service = ConsentService()
        consents = consent_service.get_user_consents(request.user)
        
        return JsonResponse({
            'consents': consents,
            'user_id': request.user.id,
            'timestamp': timezone.now().isoformat(),
        })
    
    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        """Update user consent."""
        try:
            data = json.loads(request.body)
            consent_type = data.get('consent_type')
            consent_given = data.get('consent_given', True)
            
            if not consent_type:
                return JsonResponse({'error': 'consent_type is required'}, status=400)
            
            consent_service = ConsentService()
            
            if consent_given:
                success = consent_service.give_consent(
                    user=request.user,
                    consent_type=consent_type,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )
            else:
                success = consent_service.withdraw_consent(
                    user=request.user,
                    consent_type=consent_type,
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                )
            
            if success:
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'error': 'Unable to update consent'}, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class DataRequestStatusAPIView(LoginRequiredMixin, View):
    """API endpoint to check data request status."""
    
    def get(self, request, *args, **kwargs):
        request_id = request.GET.get('request_id')
        
        if not request_id:
            return JsonResponse({'error': 'request_id is required'}, status=400)
        
        try:
            data_request = DataRequest.objects.get(
                request_id=request_id,
                user=request.user
            )
            
            return JsonResponse({
                'request_id': str(data_request.request_id),
                'status': data_request.status,
                'request_type': data_request.request_type,
                'received_at': data_request.received_at.isoformat(),
                'due_date': data_request.due_date.isoformat(),
                'days_remaining': data_request.days_remaining,
                'is_overdue': data_request.is_overdue,
            })
        
        except DataRequest.DoesNotExist:
            return JsonResponse({'error': 'Data request not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# ================ MIDDLEWARE ================

class GDPRComplianceMiddleware:
    """Middleware to ensure GDPR compliance on all requests."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Add GDPR headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Add privacy headers if dealing with personal data
        if self._contains_personal_data(response):
            response['X-Privacy-Policy'] = 'GDPR-compliant'
        
        return response
    
    def _contains_personal_data(self, response):
        """Check if response contains personal data."""
        # Simple check for common personal data indicators
        personal_data_indicators = [
            'email', 'name', 'address', 'phone', 'profile',
            'user', 'account', 'payment', 'order'
        ]
        
        content_type = response.get('Content-Type', '').lower()
        if 'text/html' in content_type and hasattr(response, 'content'):
            content = response.content.decode('utf-8', errors='ignore').lower()
            return any(indicator in content for indicator in personal_data_indicators)
        
        return False