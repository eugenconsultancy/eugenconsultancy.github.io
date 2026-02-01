"""
Forms for file uploads.
"""
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator

from apps.orders.models import OrderFile


class OrderFileForm(forms.ModelForm):
    """Form for uploading order files."""
    
    file = forms.FileField(
        label=_('File'),
        required=True,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'zip', 'rar']
            )
        ],
        help_text=_('Upload relevant order files (max 20MB)')
    )
    
    description = forms.CharField(
        label=_('Description'),
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Brief description of the file contents...'
        })
    )
    
    class Meta:
        model = OrderFile
        fields = ['file_type', 'file', 'description']
        widgets = {
            'file_type': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def clean_file(self):
        """Validate file size."""
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file size (20MB limit for order files)
            max_size = 20 * 1024 * 1024  # 20MB in bytes
            if file.size > max_size:
                raise forms.ValidationError(
                    f'File size must be under {max_size/(1024*1024)}MB.'
                )
        
        return file