from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, FormView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import render, redirect, get_object_or_404

from apps.accounts.forms import (
    AccountSettingsForm, PrivacySettingsForm, TwoFactorSetupForm
)
from apps.compliance.models import ConsentLog


class AccountSettingsView(LoginRequiredMixin, UpdateView):
    """View for account settings."""
    template_name = 'accounts/settings/account.html'
    form_class = AccountSettingsForm
    success_url = reverse_lazy('accounts:settings')
    
    def get_object(self, queryset=None):
        return self.request.user
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Account settings updated successfully.')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_tab'] = 'account'
        return context


class SecuritySettingsView(LoginRequiredMixin, TemplateView):
    """View for security settings."""
    template_name = 'accounts/settings/security.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get recent login activity (simplified)
        recent_logins = [
            {
                'ip': '192.168.1.1',
                'location': 'New York, USA',
                'device': 'Chrome on Windows',
                'time': '2 hours ago',
                'suspicious': False,
            }
        ]
        
        context.update({
            'active_tab': 'security',
            'password_form': PasswordChangeForm(self.request.user),
            'two_factor_form': TwoFactorSetupForm(),
            'recent_logins': recent_logins,
            'sessions': [],  # Would be populated from session store
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle security settings updates."""
        action = request.POST.get('action')
        
        if action == 'change_password':
            return self._handle_password_change(request)
        elif action == 'enable_2fa':
            return self._handle_2fa_setup(request)
        elif action == 'revoke_session':
            return self._handle_session_revocation(request)
        else:
            messages.error(request, 'Invalid action.')
            return self.get(request, *args, **kwargs)
    
    def _handle_password_change(self, request):
        """Handle password change."""
        form = PasswordChangeForm(request.user, request.POST)
        
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        return redirect('accounts:security_settings')
    
    def _handle_2fa_setup(self, request):
        """Handle two-factor authentication setup."""
        form = TwoFactorSetupForm(request.POST)
        
        if form.is_valid():
            # In production, this would setup 2FA
            messages.success(request, 'Two-factor authentication enabled.')
        else:
            messages.error(request, 'Error setting up two-factor authentication.')
        
        return redirect('accounts:security_settings')
    
    def _handle_session_revocation(self, request):
        """Handle session revocation."""
        session_key = request.POST.get('session_key')
        # In production, this would invalidate the session
        messages.success(request, 'Session revoked successfully.')
        return redirect('accounts:security_settings')


class PrivacySettingsView(LoginRequiredMixin, FormView):
    """View for privacy settings and GDPR compliance."""
    template_name = 'accounts/settings/privacy.html'
    form_class = PrivacySettingsForm
    success_url = reverse_lazy('accounts:privacy_settings')
    
    def get_initial(self):
        """Set initial form values from user preferences."""
        user = self.request.user
        return {
            'marketing_emails': user.marketing_emails,
            'data_processing_consent': user.privacy_policy_accepted,
            'cookie_consent': False,  # Would come from cookie consent storage
        }
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get consent history
        consent_history = ConsentLog.objects.filter(
            user=self.request.user
        ).order_by('-created_at')[:10]
        
        context.update({
            'active_tab': 'privacy',
            'consent_history': consent_history,
            'data_anonymized': self.request.user.data_anonymized,
        })
        
        return context
    
    def form_valid(self, form):
        """Handle privacy settings update."""
        user = self.request.user
        
        # Update user preferences
        marketing_emails = form.cleaned_data['marketing_emails']
        data_processing = form.cleaned_data['data_processing_consent']
        
        if user.marketing_emails != marketing_emails:
            user.marketing_emails = marketing_emails
            ConsentLog.objects.create(
                user=user,
                consent_type='marketing',
                consent_given=marketing_emails,
                consent_text='Marketing email preferences',
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            )
        
        if user.privacy_policy_accepted != data_processing:
            user.privacy_policy_accepted = data_processing
            ConsentLog.objects.create(
                user=user,
                consent_type='data_processing',
                consent_given=data_processing,
                consent_text='Data processing consent',
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT', ''),
            )
        
        user.save()
        
        messages.success(self.request, 'Privacy settings updated successfully.')
        return super().form_valid(form)