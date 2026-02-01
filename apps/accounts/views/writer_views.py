from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, FormView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import ListView
from django.contrib.auth import get_user_model
from django.db.models import Q, Count



User = get_user_model()

from apps.accounts.forms import (
    WriterProfileForm, DocumentUploadForm, OnboardingStep1Form, OnboardingStep2Form
)
from apps.accounts.models import WriterProfile, WriterDocument, WriterVerificationStatus
from apps.accounts.services import (
    OnboardingService, DocumentService, VerificationService
)

class AdminClientListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Admin view to list and manage all clients (customers)."""
    model = User
    template_name = 'accounts/admin/client_list.html'
    context_object_name = 'clients'
    paginate_by = 20

    def test_func(self):
        """Restrict access to staff members."""
        return self.request.user.is_staff

    def get_queryset(self):
        # FIX: Changed is_writer=False to user_type='client'
        # We exclude staff to ensure we only see customers
        queryset = User.objects.filter(user_type='client').order_by('-date_joined')
        
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        """Pass search query back to template for the search input value."""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context


class WriterAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to ensure only writers can access the view."""
    
    def test_func(self):
        return self.request.user.is_writer
    
    def handle_no_permission(self):
        messages.error(self.request, 'Access restricted to writers only.')
        return redirect('accounts:dashboard')


class WriterProfileView(WriterAccessMixin, UpdateView):
    """View for writers to view and update their profile."""
    model = WriterProfile
    form_class = WriterProfileForm
    template_name = 'accounts/writer/profile.html'
    success_url = reverse_lazy('accounts:writer_profile')
    
    def get_object(self, queryset=None):
        return self.request.user.writer_profile
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['verification_status'] = self.request.user.verification_status
        context['documents'] = self.request.user.documents.all()
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Profile updated successfully.')
        return response


class WriterDocumentsView(WriterAccessMixin, TemplateView):
    """View for writers to manage their verification documents."""
    template_name = 'accounts/writer/documents.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user = self.request.user
        verification = user.verification_status
        
        # Get document statistics
        documents = user.documents.all()
        document_stats = DocumentService.get_document_stats(user.id)
        
        # Check what documents are required
        required_documents = self._get_required_documents(user)
        
        context.update({
            'documents': documents,
            'document_stats': document_stats,
            'required_documents': required_documents,
            'verification_status': verification,
            'can_upload': verification.state in ['profile_completed', 'revision_required', 'rejected'],
            'upload_form': DocumentUploadForm(),
        })
        
        return context
    
    def _get_required_documents(self, user):
        """Determine which documents are required for verification."""
        required = [
            ('id_proof', 'ID Proof (Passport/Driver\'s License)'),
            ('degree_certificate', 'Degree Certificate'),
            ('transcript', 'Academic Transcript'),
        ]
        
        # Check which required documents are already uploaded and verified
        for doc_type, display_name in required.copy():
            existing = WriterDocument.objects.filter(
                user=user,
                document_type=doc_type,
                status='verified'
            ).exists()
            
            if existing:
                required.remove((doc_type, display_name))
        
        return required
    
    def post(self, request, *args, **kwargs):
        """Handle document upload."""
        if not request.user.is_writer:
            messages.error(request, 'Access restricted to writers only.')
            return redirect('accounts:dashboard')
        
        verification = request.user.verification_status
        
        # Check if user can upload documents
        if verification.state not in ['profile_completed', 'revision_required', 'rejected']:
            messages.error(request, 'Cannot upload documents at this stage.')
            return redirect('accounts:writer_documents')
        
        form = DocumentUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                document = DocumentService.upload_document(
                    user=request.user,
                    document_type=form.cleaned_data['document_type'],
                    file_obj=form.cleaned_data['document'],
                    description=form.cleaned_data.get('description', '')
                )
                
                messages.success(
                    request,
                    f'{document.get_document_type_display()} uploaded successfully.'
                )
                
            except Exception as e:
                messages.error(request, f'Error uploading document: {str(e)}')
        
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        return redirect('accounts:writer_documents')


class VerificationStatusView(WriterAccessMixin, TemplateView):
    """View for writers to check their verification status."""
    template_name = 'accounts/writer/verification_status.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user = self.request.user
        verification = user.verification_status
        
        # Get onboarding status
        onboarding_status = OnboardingService.get_onboarding_status(user.id)
        
        # Get verification queue position (if applicable)
        queue_position = self._get_queue_position(verification)
        
        # Get timeline events
        timeline = self._get_verification_timeline(verification)
        
        context.update({
            'verification': verification,
            'onboarding_status': onboarding_status,
            'queue_position': queue_position,
            'timeline': timeline,
            'documents': user.documents.all(),
            'next_steps': self._get_next_steps(verification),
        })
        
        return context
    
    def _get_queue_position(self, verification):
        """Get position in verification queue if applicable."""
        if verification.state not in ['documents_submitted', 'under_admin_review']:
            return None
        
        # Count submissions before this one
        position = WriterVerificationStatus.objects.filter(
            state='documents_submitted',
            documents_submitted_at__lt=verification.documents_submitted_at
        ).count() + 1
        
        return position
    
    def _get_verification_timeline(self, verification):
        """Create timeline of verification events."""
        timeline = []
        
        # Registration
        timeline.append({
            'event': 'Registered',
            'date': verification.created_at,
            'completed': True,
            'description': 'Account created on EBWriting platform',
        })
        
        # Profile completion
        if verification.profile_completed_at:
            timeline.append({
                'event': 'Profile Completed',
                'date': verification.profile_completed_at,
                'completed': True,
                'description': 'Writer profile information submitted',
            })
        
        # Documents submission
        if verification.documents_submitted_at:
            timeline.append({
                'event': 'Documents Submitted',
                'date': verification.documents_submitted_at,
                'completed': True,
                'description': 'Verification documents uploaded',
            })
        
        # Review started
        if verification.review_started_at:
            timeline.append({
                'event': 'Review Started',
                'date': verification.review_started_at,
                'completed': True,
                'description': 'Admin review process initiated',
            })
        
        # Review completed
        if verification.review_completed_at:
            timeline.append({
                'event': 'Review Completed',
                'date': verification.review_completed_at,
                'completed': True,
                'description': f'Verification {verification.get_state_display()}',
            })
        
        # Future steps (if not completed)
        if not verification.review_completed_at:
            if verification.state == 'documents_submitted':
                timeline.append({
                    'event': 'Admin Review',
                    'date': None,
                    'completed': False,
                    'description': 'Waiting for admin to start review',
                })
            elif verification.state == 'under_admin_review':
                timeline.append({
                    'event': 'Decision',
                    'date': None,
                    'completed': False,
                    'description': 'Admin reviewing your submission',
                })
        
        return timeline
    
    def _get_next_steps(self, verification):
        """Get next steps based on current state."""
        steps = []
        
        if verification.state == 'registered':
            steps.append('Complete your writer profile')
            steps.append('Upload required verification documents')
        
        elif verification.state == 'profile_completed':
            steps.append('Upload at least 3 verification documents')
            steps.append('Submit documents for admin review')
        
        elif verification.state == 'documents_submitted':
            steps.append('Wait for admin review (typically 2-3 business days)')
            steps.append('Check email for updates')
        
        elif verification.state == 'under_admin_review':
            steps.append('Wait for final decision')
            steps.append('Check email regularly for updates')
        
        elif verification.state == 'rejected':
            steps.append('Review rejection reason')
            steps.append('Update documents as needed')
            steps.append('Resubmit for verification')
        
        elif verification.state == 'revision_required':
            steps.append('Review revision notes')
            steps.append('Update requested documents')
            steps.append('Resubmit for verification')
        
        elif verification.state == 'approved':
            steps.append('Complete your profile details')
            steps.append('Set your availability')
            steps.append('Start browsing available orders')
        
        return steps


class WriterOnboardingStep1View(WriterAccessMixin, FormView):
    """View for step 1 of writer onboarding (profile completion)."""
    template_name = 'accounts/writer/step1_profile.html'
    form_class = OnboardingStep1Form
    success_url = reverse_lazy('accounts:writer_onboarding_step2')
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is at the right step
        verification = request.user.verification_status
        if verification.state != 'registered':
            messages.info(request, 'Profile already completed or not at this step.')
            return redirect('accounts:dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.request.user.writer_profile
        return kwargs
    
    def form_valid(self, form):
        try:
            # Update writer profile
            writer_profile = form.save(commit=False)
            writer_profile.profile_completed_at = timezone.now()
            writer_profile.status = 'active'
            writer_profile.save()
            
            # Update verification state
            verification = self.request.user.verification_status
            verification.complete_profile()
            verification.save()
            
            messages.success(self.request, 'Profile completed successfully!')
            return super().form_valid(form)
            
        except Exception as e:
            messages.error(self.request, f'Error saving profile: {str(e)}')
            return self.form_invalid(form)


class WriterOnboardingStep2View(WriterAccessMixin, TemplateView):
    """View for step 2 of writer onboarding (document submission)."""
    template_name = 'accounts/writer/step2_documents.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is at the right step
        verification = request.user.verification_status
        if verification.state != 'profile_completed':
            messages.info(request, 'Not at document submission step.')
            return redirect('accounts:dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user = self.request.user
        required_documents = [
            ('id_proof', 'ID Proof (Passport/Driver\'s License)', 
             'Upload a clear photo/scan of your government-issued ID'),
            ('degree_certificate', 'Degree Certificate',
             'Upload your highest degree certificate'),
            ('transcript', 'Academic Transcript',
             'Upload your official academic transcript'),
            ('cv', 'Curriculum Vitae',
             'Upload your professional CV/resume (optional but recommended)'),
            ('portfolio', 'Writing Portfolio',
             'Upload samples of your academic writing (optional but recommended)'),
        ]
        
        # Check which documents are already uploaded
        uploaded_docs = {}
        for doc in user.documents.all():
            uploaded_docs[doc.document_type] = {
                'status': doc.status,
                'verified': doc.status == 'verified',
                'file': doc.document.name.split('/')[-1],
                'uploaded_at': doc.created_at,
            }
        
        context.update({
            'required_documents': required_documents,
            'uploaded_docs': uploaded_docs,
            'upload_form': DocumentUploadForm(),
            'verification': user.verification_status,
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle document upload or submission for review."""
        action = request.POST.get('action')
        
        if action == 'upload':
            return self._handle_document_upload(request)
        elif action == 'submit':
            return self._handle_submission(request)
        else:
            messages.error(request, 'Invalid action.')
            return redirect('accounts:writer_onboarding_step2')
    
    def _handle_document_upload(self, request):
        """Handle document upload."""
        form = DocumentUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                document = DocumentService.upload_document(
                    user=request.user,
                    document_type=form.cleaned_data['document_type'],
                    file_obj=form.cleaned_data['document'],
                    description=form.cleaned_data.get('description', '')
                )
                
                messages.success(
                    request,
                    f'{document.get_document_type_display()} uploaded successfully.'
                )
                
                # Check if user now has enough documents to submit
                verified_count = request.user.documents.filter(status='verified').count()
                if verified_count >= 3:
                    messages.info(
                        request,
                        'You now have enough verified documents to submit for review.'
                    )
                
            except Exception as e:
                messages.error(request, f'Error uploading document: {str(e)}')
        
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        return redirect('accounts:writer_onboarding_step2')
    
    def _handle_submission(self, request):
        """Handle submission for admin review."""
        try:
            # Verify minimum requirements
            verified_count = request.user.documents.filter(status='verified').count()
            if verified_count < 3:
                messages.error(
                    request,
                    f'Need at least 3 verified documents. Currently have: {verified_count}'
                )
                return redirect('accounts:writer_onboarding_step2')
            
            # Submit for verification
            VerificationService.submit_for_verification(request.user)
            
            messages.success(
                request,
                'Documents submitted for admin review. You will be notified via email.'
            )
            
            return redirect('accounts:verification_status')
            
        except Exception as e:
            messages.error(request, f'Error submitting for review: {str(e)}')
            return redirect('accounts:writer_onboarding_step2')
        
class AdminWriterListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Admin view to list and manage all writers in the system."""
    model = User
    template_name = 'accounts/admin/writer_list.html'
    context_object_name = 'writers'
    paginate_by = 20

    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        messages.error(self.request, 'You do not have permission to access the writer management panel.')
        return redirect('accounts:dashboard')

    def get_queryset(self):
        # Base queryset for writers
        queryset = User.objects.filter(user_type='writer').select_related('verification_status').order_by('-date_joined')
        
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )
        
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(verification_status__state=status_filter)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 1. Provide status choices for the filter dropdown
        context['status_choices'] = WriterVerificationStatus.STATE_CHOICES
        
        # 2. Get counts for the stats cards (The "Logic" fix)
        # This counts how many writers exist for each verification state
        status_counts = WriterVerificationStatus.objects.values('state').annotate(total=Count('state'))
        
        # Convert list of dicts to a simple dict for template access: e.g., {'pending': 5, 'approved': 10}
        counts_dict = {item['state']: item['total'] for item in status_counts}
        context['status_totals'] = counts_dict
        
        context['search_query'] = self.request.GET.get('search', '')
        context['current_status'] = self.request.GET.get('status', '')
        return context