"""
Forms for plagiarism detection (admin interface).
"""
from django import forms

from .models import PlagiarismCheck, PlagiarismPolicy


class PlagiarismCheckForm(forms.ModelForm):
    """
    Form for manually requesting plagiarism checks.
    """
    class Meta:
        model = PlagiarismCheck
        fields = ['order', 'source']
        widgets = {
            'order': forms.Select(attrs={'class': 'form-select'}),
            'source': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        """
        Initialize form with available sources.
        """
        super().__init__(*args, **kwargs)
        from .api_clients import PlagiarismClientFactory
        available_sources = PlagiarismClientFactory.get_available_clients()
        
        source_choices = [(source, source.capitalize()) for source in available_sources]
        self.fields['source'].choices = source_choices


class PlagiarismPolicyForm(forms.ModelForm):
    """
    Form for managing plagiarism policies.
    """
    class Meta:
        model = PlagiarismPolicy
        fields = [
            'name', 'description',
            'warning_threshold', 'action_threshold', 'rejection_threshold',
            'warning_action', 'critical_action',
            'order_types', 'client_tiers',
            'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'warning_action': forms.Textarea(attrs={'rows': 2}),
            'critical_action': forms.Textarea(attrs={'rows': 2}),
            'order_types': forms.TextInput(attrs={'placeholder': '["essay", "dissertation"]'}),
            'client_tiers': forms.TextInput(attrs={'placeholder': '["standard", "premium"]'}),
        }
    
    def clean(self):
        """
        Validate threshold values.
        """
        cleaned_data = super().clean()
        
        warning = cleaned_data.get('warning_threshold')
        action = cleaned_data.get('action_threshold')
        rejection = cleaned_data.get('rejection_threshold')
        
        if warning and action and warning >= action:
            self.add_error('warning_threshold', 
                          "Warning threshold must be less than action threshold")
        
        if action and rejection and action >= rejection:
            self.add_error('action_threshold',
                          "Action threshold must be less than rejection threshold")
        
        return cleaned_data