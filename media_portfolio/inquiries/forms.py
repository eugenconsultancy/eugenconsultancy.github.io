from django import forms
from .models import Inquiry
from ..media.models import MediaItem


class InquiryForm(forms.ModelForm):
    """
    Form for client inquiries
    """
    media_item = forms.ModelChoiceField(
        queryset=MediaItem.objects.filter(is_published=True),
        required=False,
        empty_label="Select a specific piece (optional)",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = Inquiry
        fields = [
            'inquiry_type', 'media_item', 'name', 'email', 'phone',
            'company', 'subject', 'message', 'usage_type', 'deadline',
            'budget_range', 'accepted_terms', 'accepted_privacy'
        ]
        widgets = {
            'inquiry_type': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 234 567 8900'}),
            'company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company/Organization (optional)'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'What is this regarding?'}),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Please provide details about your inquiry...'
            }),
            'usage_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Website, Print, Exhibition'
            }),
            'deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'budget_range': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., $500-$1000'
            }),
            'accepted_terms': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'accepted_privacy': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make optional fields clear
        self.fields['phone'].required = False
        self.fields['company'].required = False
        self.fields['usage_type'].required = False
        self.fields['deadline'].required = False
        self.fields['budget_range'].required = False

    def clean(self):
        cleaned_data = super().clean()
        inquiry_type = cleaned_data.get('inquiry_type')
        
        # Validate based on inquiry type
        if inquiry_type in ['license', 'print'] and not cleaned_data.get('media_item'):
            self.add_error('media_item', 'Please select the media item for licensing/print inquiry')
        
        if inquiry_type == 'commission' and not cleaned_data.get('budget_range'):
            self.add_error('budget_range', 'Please provide a budget range for commission work')
        
        # Validate legal acceptance
        if not cleaned_data.get('accepted_terms'):
            self.add_error('accepted_terms', 'You must accept the terms and conditions')
        
        if not cleaned_data.get('accepted_privacy'):
            self.add_error('accepted_privacy', 'You must accept the privacy policy')
        
        return cleaned_data