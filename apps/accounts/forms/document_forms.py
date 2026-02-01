from django import forms
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import WriterDocument


class DocumentUploadForm(forms.ModelForm):
    """Form for uploading writer verification documents."""
    
    document_type = forms.ChoiceField(
        label=_('Document type'),
        choices=WriterDocument.DocumentType.choices,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'data-max-size': '10MB',
        }),
        help_text=_('Select the type of document you are uploading'),
    )
    
    document = forms.FileField(
        label=_('Document file'),
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx',
        }),
        help_text=_(
            'Upload PDF, JPG, PNG, DOC, or DOCX file. '
            'Maximum file size is 10MB.'
        ),
    )
    
    description = forms.CharField(
        label=_('Description (optional)'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Brief description of this document...',
        }),
        required=False,
        max_length=500,
    )
    
    confirm_authenticity = forms.BooleanField(
        label=_('I confirm this document is authentic and belongs to me'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must confirm the authenticity of this document.')
        },
    )
    
    agree_to_verification = forms.BooleanField(
        label=_('I agree to this document being verified by EBWriting administrators'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must agree to document verification.')
        },
    )
    
    class Meta:
        model = WriterDocument
        fields = ('document_type', 'document', 'description')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Limit document types based on what's already uploaded
        if 'initial' in kwargs and 'user' in kwargs['initial']:
            user = kwargs['initial']['user']
            existing_docs = user.documents.filter(
                status__in=['pending', 'verified']
            ).values_list('document_type', flat=True)
            
            # Remove already uploaded types from choices
            choices = list(self.fields['document_type'].choices)
            choices = [(value, label) for value, label in choices 
                      if value not in existing_docs]
            self.fields['document_type'].choices = choices
    
    def clean_document(self):
        """Validate uploaded document."""
        document = self.cleaned_data.get('document')
        
        if not document:
            raise forms.ValidationError(_('No document uploaded.'))
        
        # Check file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB
        if document.size > max_size:
            raise forms.ValidationError(
                _('File size must be under 10MB.')
            )
        
        # Check file extension
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
        filename = document.name.lower()
        
        if not any(filename.endswith(ext) for ext in allowed_extensions):
            raise forms.ValidationError(
                _('File type not allowed. Allowed types: PDF, JPG, PNG, DOC, DOCX.')
            )
        
        return document


class DocumentVerificationForm(forms.ModelForm):
    """Form for admin verification of documents."""
    
    status = forms.ChoiceField(
        label=_('Verification status'),
        choices=[
            ('verified', 'Verified'),
            ('rejected', 'Rejected'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )
    
    review_notes = forms.CharField(
        label=_('Review notes'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Add notes about this verification...',
        }),
        required=False,
        help_text=_('Internal notes for other administrators'),
    )
    
    rejection_reason = forms.CharField(
        label=_('Rejection reason'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Explain why this document was rejected...',
        }),
        required=False,
        help_text=_('This will be shown to the writer'),
    )
    
    expires_in_days = forms.IntegerField(
        label=_('Expires in (days)'),
        initial=365,
        min_value=30,
        max_value=730,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text=_('Document validity period in days'),
    )
    
    class Meta:
        model = WriterDocument
        fields = ('status', 'review_notes', 'rejection_reason')
    
    def clean(self):
        """Validate verification form."""
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        if status == 'rejected' and not rejection_reason:
            raise forms.ValidationError({
                'rejection_reason': _('Rejection reason is required when rejecting a document.')
            })
        
        return cleaned_data