from django import forms
from django.utils.translation import gettext_lazy as _

from apps.compliance.models import DataRequest


class DataRequestForm(forms.ModelForm):
    """Form for submitting GDPR data requests."""
    
    request_type = forms.ChoiceField(
        label=_('Request type'),
        choices=DataRequest.RequestType.choices,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'onchange': 'toggleCustomReason()',
        }),
        help_text=_('Select the type of data request'),
    )
    
    description = forms.CharField(
        label=_('Description'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Please describe your request in detail...',
        }),
        max_length=2000,
        help_text=_('Provide detailed information about your request'),
    )
    
    custom_reason = forms.CharField(
        label=_('Additional details (if "Other" is selected)'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Please specify...',
            'style': 'display: none;',
        }),
        required=False,
        max_length=1000,
    )
    
    confirm_identity = forms.BooleanField(
        label=_('I confirm I am the account holder or their authorized representative'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must confirm your identity to submit this request.')
        },
    )
    
    agree_to_verification = forms.BooleanField(
        label=_('I agree to provide additional verification if required'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must agree to verification procedures.')
        },
    )
    
    understand_timeline = forms.BooleanField(
        label=_('I understand this request may take up to 30 days to process'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must acknowledge the processing timeline.')
        },
    )
    
    class Meta:
        model = DataRequest
        fields = ('request_type', 'description')
    
    def clean(self):
        """Validate data request form."""
        cleaned_data = super().clean()
        request_type = cleaned_data.get('request_type')
        custom_reason = cleaned_data.get('custom_reason')
        
        if request_type == 'other' and not custom_reason:
            raise forms.ValidationError({
                'custom_reason': _('Please specify the reason for your request.')
            })
        
        return cleaned_data
    
    def clean_description(self):
        """Validate request description."""
        description = self.cleaned_data.get('description', '').strip()
        
        if len(description) < 20:
            raise forms.ValidationError(
                _('Please provide a more detailed description (at least 20 characters).')
            )
        
        if len(description) > 2000:
            raise forms.ValidationError(
                _('Description is too long (maximum 2000 characters).')
            )
        
        return description


class ConsentWithdrawalForm(forms.Form):
    """Form for withdrawing consent."""
    
    consent_type = forms.ChoiceField(
        label=_('Consent to withdraw'),
        choices=[
            ('marketing', 'Marketing emails'),
            ('cookies', 'Non-essential cookies'),
            ('data_processing', 'Data processing (will delete account)'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        help_text=_('Select which consent you wish to withdraw'),
    )
    
    reason = forms.CharField(
        label=_('Reason for withdrawal (optional)'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Please tell us why you are withdrawing consent...',
        }),
        required=False,
        max_length=1000,
        help_text=_('Helps us improve our services'),
    )
    
    confirm_withdrawal = forms.BooleanField(
        label=_('I understand the consequences of withdrawing this consent'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must confirm you understand the consequences.')
        },
    )
    
    def clean(self):
        """Validate consent withdrawal form."""
        cleaned_data = super().clean()
        consent_type = cleaned_data.get('consent_type')
        
        if consent_type == 'data_processing':
            # Add additional warnings for data processing withdrawal
            self.add_warning(
                'Withdrawing data processing consent will result in account deletion '
                'in accordance with GDPR regulations.'
            )
        
        return cleaned_data