"""
Forms for dispute resolution (web interface).
"""
from django import forms
from django.utils import timezone

from .models import Dispute, DisputeEvidence, DisputeMessage
from apps.orders.models import Order


class DisputeForm(forms.ModelForm):
    """
    Form for opening disputes.
    """
    class Meta:
        model = Dispute
        fields = ['reason', 'title', 'description', 'requested_refund_amount', 'priority']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'requested_refund_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        """
        Initialize form with order context.
        """
        self.order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
        
        if self.order:
            # Set initial refund amount to order amount
            self.fields['requested_refund_amount'].initial = self.order.amount
    
    def clean(self):
        """
        Validate dispute form.
        """
        cleaned_data = super().clean()
        
        if self.order:
            # Check if order can be disputed
            if self.order.status not in ['delivered', 'in_progress', 'completed']:
                raise forms.ValidationError(
                    f"Cannot open dispute for order in status: {self.order.status}"
                )
            
            # Check for existing active dispute
            existing_dispute = Dispute.objects.filter(
                order=self.order,
                status__in=['opened', 'under_review', 'awaiting_response', 'evidence_review']
            ).exists()
            
            if existing_dispute:
                raise forms.ValidationError(
                    "An active dispute already exists for this order"
                )
        
        return cleaned_data


class EvidenceSubmissionForm(forms.ModelForm):
    """
    Form for submitting evidence.
    """
    class Meta:
        model = DisputeEvidence
        fields = ['evidence_type', 'title', 'description', 'content']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'content': forms.Textarea(attrs={'rows': 4}),
            'evidence_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
        }


class DisputeResolutionForm(forms.Form):
    """
    Form for proposing dispute resolutions.
    """
    RESOLUTION_CHOICES = [
        ('full_refund', 'Full Refund'),
        ('partial_refund', 'Partial Refund'),
        ('revision_required', 'Revision Required'),
        ('new_writer_assigned', 'New Writer Assigned'),
        ('compensation', 'Compensation'),
        ('mutual_agreement', 'Mutual Agreement'),
    ]
    
    resolution_type = forms.ChoiceField(
        choices=RESOLUTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    resolution_details = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        required=True
    )
    refund_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    def clean(self):
        """
        Validate resolution form.
        """
        cleaned_data = super().clean()
        
        resolution_type = cleaned_data.get('resolution_type')
        refund_amount = cleaned_data.get('refund_amount')
        
        if resolution_type in ['full_refund', 'partial_refund']:
            if not refund_amount:
                raise forms.ValidationError(
                    "Refund amount is required for refund resolutions"
                )
            if refund_amount <= 0:
                raise forms.ValidationError(
                    "Refund amount must be positive"
                )
        
        return cleaned_data


class DisputeMessageForm(forms.ModelForm):
    """
    Form for sending dispute messages.
    """
    class Meta:
        model = DisputeMessage
        fields = ['content', 'message_type']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'message_type': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        """
        Initialize form with user context.
        """
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set message type based on user role
        if self.user and self.user.is_staff:
            self.fields['message_type'].choices = DisputeMessage.MESSAGE_TYPES
        else:
            # Non-admin users can only send external messages
            self.fields['message_type'].choices = [
                ('external', 'External (Visible to Parties)')
            ]
            self.fields['message_type'].initial = 'external'