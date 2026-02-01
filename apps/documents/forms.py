# apps/documents/forms.py
from django import forms
from django.core.validators import FileExtensionValidator

from apps.documents.models import (
    DocumentTemplate,
    GeneratedDocument
)


class DocumentFilterForm(forms.Form):
    """Form for filtering documents."""
    
    DOCUMENT_TYPES = [
        ('', 'All Types'),
        ('invoice', 'Invoice'),
        ('order_summary', 'Order Summary'),
        ('delivery_cover', 'Delivery Cover'),
        ('completion_certificate', 'Completion Certificate'),
        ('refund_receipt', 'Refund Receipt'),
        ('agreement', 'Agreement'),
        ('report', 'Report'),
    ]
    
    SIGNED_CHOICES = [
        ('', 'All'),
        ('signed', 'Signed Only'),
        ('unsigned', 'Unsigned Only'),
    ]
    
    ARCHIVED_CHOICES = [
        ('', 'All'),
        ('archived', 'Archived Only'),
        ('active', 'Active Only'),
    ]
    
    document_type = forms.ChoiceField(
        choices=DOCUMENT_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    order_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by Order ID'
        })
    )
    
    signed = forms.ChoiceField(
        choices=SIGNED_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    archived = forms.ChoiceField(
        choices=ARCHIVED_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    def clean_order_id(self):
        order_id = self.cleaned_data.get('order_id', '').strip()
        if order_id and not order_id.startswith('#'):
            order_id = f"#{order_id}"
        return order_id
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("Start date cannot be after end date")
        
        return cleaned_data


class DocumentTemplateForm(forms.ModelForm):
    """Form for document templates."""
    
    class Meta:
        model = DocumentTemplate
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
            'template_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.html,.tex,.docx'
            }),
            'template_content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 15,
                'placeholder': 'Enter template content with placeholders like {{user_name}}'
            }),
            'placeholders': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'JSON array of placeholders. Example: [{"name": "user_name", "description": "Full name of the user"}]'
            }),
            'styles': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'JSON object of CSS styles. Example: {"body": {"font-family": "Arial"}}'
            }),
            'allowed_signers': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'JSON array of allowed signer roles. Example: ["admin", "writer"]'
            })
        }
    
    def clean(self):
        cleaned_data = super().clean()
        template_file = cleaned_data.get('template_file')
        template_content = cleaned_data.get('template_content')
        
        # Ensure either file or content is provided
        if not template_file and not template_content:
            raise forms.ValidationError(
                "Either template file or template content must be provided"
            )
        
        return cleaned_data
    
    def clean_placeholders(self):
        """Validate placeholders JSON."""
        import json
        placeholders = self.cleaned_data.get('placeholders', '[]')
        
        try:
            parsed = json.loads(placeholders)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Placeholders must be a JSON array")
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


class DocumentSignForm(forms.Form):
    """Form for signing documents."""
    
    verification_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 6-digit verification code',
            'pattern': '[0-9]{6}'
        }),
        help_text="Enter the 6-digit verification code sent to your email"
    )
    
    agree_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I agree that I am signing this document electronically and that this signature is legally binding"
    )
    
    def clean_verification_code(self):
        code = self.cleaned_data.get('verification_code', '').strip()
        if not code.isdigit() or len(code) != 6:
            raise forms.ValidationError("Verification code must be 6 digits")
        return code


class GenerateDocumentForm(forms.Form):
    """Form for generating documents from templates."""
    
    template = forms.ModelChoiceField(
        queryset=DocumentTemplate.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    user_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter user email'
        })
    )
    
    order_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Optional: Order ID'
        })
    )
    
    document_title = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter document title'
        })
    )
    
    custom_data = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Optional: JSON data for template placeholders'
        }),
        help_text="Enter JSON data for template placeholders"
    )
    
    def clean_order_id(self):
        order_id = self.cleaned_data.get('order_id', '').strip()
        if order_id and not order_id.startswith('#'):
            order_id = f"#{order_id}"
        return order_id
    
    def clean_custom_data(self):
        import json
        data = self.cleaned_data.get('custom_data', '{}')
        
        if not data:
            return '{}'
        
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Custom data must be a JSON object")
            return data
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format for custom data")