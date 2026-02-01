# apps/notifications/forms.py
from django import forms
from django.utils import timezone

from apps.notifications.models import (
    NotificationPreference,
    EmailTemplate
)


class NotificationPreferenceForm(forms.ModelForm):
    """Form for notification preferences."""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'email_enabled',
            'push_enabled',
            'sms_enabled',
            'quiet_hours_enabled',
            'quiet_hours_start',
            'quiet_hours_end',
            'daily_email_limit'
        ]
        widgets = {
            'quiet_hours_start': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'quiet_hours_end': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'daily_email_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 100
            })
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate quiet hours
        quiet_hours_enabled = cleaned_data.get('quiet_hours_enabled', False)
        quiet_hours_start = cleaned_data.get('quiet_hours_start')
        quiet_hours_end = cleaned_data.get('quiet_hours_end')
        
        if quiet_hours_enabled:
            if not quiet_hours_start or not quiet_hours_end:
                raise forms.ValidationError(
                    "Both start and end times are required for quiet hours"
                )
            
            if quiet_hours_start == quiet_hours_end:
                raise forms.ValidationError(
                    "Quiet hours start and end times cannot be the same"
                )
        
        return cleaned_data


class EmailTemplateForm(forms.ModelForm):
    """Form for email templates."""
    
    class Meta:
        model = EmailTemplate
        fields = [
            'name',
            'description',
            'template_type',
            'format',
            'template_file',
            'template_content',
            'placeholders',
            'styles',
            'is_active',
            'requires_signature',
            'allowed_signers'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter template name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe the template purpose'
            }),
            'template_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'format': forms.Select(attrs={
                'class': 'form-control'
            }),
            'template_content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Enter template content with placeholders like {{user_name}}'
            }),
            'placeholders': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'JSON array of available placeholders'
            }),
            'styles': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'JSON object of CSS styles'
            }),
            'allowed_signers': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'JSON array of allowed signer roles'
            })
        }
    
    def clean_placeholders(self):
        """Validate placeholders JSON."""
        import json
        placeholders = self.cleaned_data.get('placeholders', '[]')
        
        try:
            parsed = json.loads(placeholders)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Placeholders must be a JSON array")
            
            # Validate each placeholder
            for item in parsed:
                if not isinstance(item, dict):
                    raise forms.ValidationError("Each placeholder must be an object")
                if 'name' not in item or 'description' not in item:
                    raise forms.ValidationError("Placeholder must have name and description")
            
            return placeholders
            
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format for placeholders")
    
    def clean_styles(self):
        """Validate styles JSON."""
        import json
        styles = self.cleaned_data.get('styles', '{}')
        
        try:
            parsed = json.loads(styles)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Styles must be a JSON object")
            return styles
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format for styles")
    
    def clean_allowed_signers(self):
        """Validate allowed signers JSON."""
        import json
        signers = self.cleaned_data.get('allowed_signers', '[]')
        
        try:
            parsed = json.loads(signers)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Allowed signers must be a JSON array")
            return signers
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format for allowed signers")


class TestNotificationForm(forms.Form):
    """Form for testing notifications."""
    
    NOTIFICATION_TYPES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('alert', 'Alert'),
        ('success', 'Success'),
        ('error', 'Error'),
    ]
    
    CHANNELS = [
        ('email', 'Email Only'),
        ('push', 'Push Notification Only'),
        ('in_app', 'In-App Only'),
        ('all', 'All Channels'),
    ]
    
    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter notification title'
        })
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter notification message'
        })
    )
    
    notification_type = forms.ChoiceField(
        choices=NOTIFICATION_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    channels = forms.ChoiceField(
        choices=CHANNELS,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    priority = forms.ChoiceField(
        choices=[(i, f'Priority {i}') for i in range(1, 5)],
        initial=2,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    action_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional: URL for action button'
        })
    )
    
    action_text = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional: Text for action button'
        })
    )