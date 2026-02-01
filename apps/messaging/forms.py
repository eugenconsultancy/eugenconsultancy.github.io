# apps/messaging/forms.py
from django import forms
from django.core.validators import FileExtensionValidator

from apps.messaging.models import Message, MessageAttachment


class SendMessageForm(forms.Form):
    """Form for sending messages."""
    
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Type your message here...',
            'maxlength': 5000
        }),
        required=True,
        min_length=1,
        max_length=5000
    )
    
    attachments = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'multiple': True,
            'accept': ','.join([
                '.pdf', '.doc', '.docx', '.txt', '.rtf',
                '.jpg', '.jpeg', '.png', '.gif',
                '.xls', '.xlsx', '.ppt', '.pptx'
            ])
        }),
        required=False,
        validators=[
            FileExtensionValidator(allowed_extensions=[
                'pdf', 'doc', 'docx', 'txt', 'rtf',
                'jpg', 'jpeg', 'png', 'gif',
                'xls', 'xlsx', 'ppt', 'pptx'
            ])
        ]
    )
    
    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise forms.ValidationError("Message cannot be empty")
        return content
    
    def clean_attachments(self):
        attachments = self.files.getlist('attachments')
        
        # Check number of attachments
        if len(attachments) > 5:
            raise forms.ValidationError("Maximum 5 attachments allowed")
        
        # Check file sizes
        for attachment in attachments:
            if attachment.size > 10 * 1024 * 1024:  # 10MB
                raise forms.ValidationError(
                    f"File {attachment.name} exceeds 10MB limit"
                )
        
        return attachments


class ConversationFilterForm(forms.Form):
    """Form for filtering conversations."""
    
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('open', 'Open'),
        ('closed', 'Closed'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
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
    
    def clean_order_id(self):
        order_id = self.cleaned_data.get('order_id', '').strip()
        if order_id and not order_id.startswith('#'):
            order_id = f"#{order_id}"
        return order_id