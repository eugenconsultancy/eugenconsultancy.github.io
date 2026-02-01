from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator


class AdminAssignmentForm(forms.Form):
    """Form for admin assignment of orders to writers."""
    
    order_id = forms.IntegerField(
        label=_('Order ID'),
        widget=forms.HiddenInput(),
        required=True,
    )
    
    writer_id = forms.IntegerField(
        label=_('Writer'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        help_text=_('Select a writer to assign this order to'),
    )
    
    assignment_notes = forms.CharField(
        label=_('Assignment notes (optional)'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add any notes for the writer about this assignment...',
        }),
        required=False,
        max_length=1000,
        help_text=_('Internal notes about why this writer was selected'),
    )
    
    notify_writer = forms.BooleanField(
        label=_('Notify writer about assignment'),
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Send email notification to the writer'),
    )
    
    priority = forms.ChoiceField(
        label=_('Assignment priority'),
        choices=[
            ('normal', 'Normal Priority'),
            ('high', 'High Priority'),
            ('urgent', 'Urgent - Nearing Deadline'),
        ],
        initial='normal',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text=_('Set the priority level for this assignment'),
    )
    
    def __init__(self, *args, **kwargs):
        """Populate writer choices."""
        super().__init__(*args, **kwargs)
        
        # Get available writers
        from apps.accounts.models import User
        
        available_writers = User.objects.filter(
            user_type='writer',
            writer_profile__is_available=True,
            verification_status__state='approved',
        ).select_related('writer_profile')
        
        # Create choices
        writer_choices = [(0, '--- Select a Writer ---')]
        for writer in available_writers:
            display_name = f'{writer.get_full_name()} ({writer.email}) - '
            display_name += f'Load: {writer.writer_profile.current_orders}/{writer.writer_profile.max_orders} - '
            display_name += f'Rating: {writer.writer_profile.average_rating}/5.0'
            
            writer_choices.append((writer.id, display_name))
        
        self.fields['writer_id'].widget.choices = writer_choices
    
    def clean_writer_id(self):
        """Validate writer selection."""
        writer_id = self.cleaned_data.get('writer_id')
        
        if writer_id == 0:
            raise forms.ValidationError(_('Please select a writer.'))
        
        # Check if writer exists and is available
        from apps.accounts.models import User
        
        try:
            writer = User.objects.get(
                id=writer_id,
                user_type='writer',
                writer_profile__is_available=True,
                verification_status__state='approved',
            )
            
            # Check writer's current load
            if not writer.writer_profile.can_accept_orders:
                raise forms.ValidationError(
                    _('Selected writer is not currently available for new assignments.')
                )
            
        except User.DoesNotExist:
            raise forms.ValidationError(_('Selected writer is not available.'))
        
        return writer_id
    
    def clean_order_id(self):
        """Validate order."""
        order_id = self.cleaned_data.get('order_id')
        
        from apps.orders.models import Order
        
        try:
            order = Order.objects.get(
                id=order_id,
                state='paid',
                writer__isnull=True,
            )
        except Order.DoesNotExist:
            raise forms.ValidationError(
                _('Order is not available for assignment.')
            )
        
        return order_id


class DisputeResolutionForm(forms.Form):
    """Form for resolving order disputes."""
    
    RESOLUTION_CHOICES = [
        ('full_refund', 'Full Refund to Client'),
        ('partial_refund', 'Partial Refund to Client'),
        ('writer_payment', 'Release Payment to Writer'),
        ('split_payment', 'Split Payment (Partial Refund)'),
        ('reopen_order', 'Reopen Order for Revision'),
        ('no_action', 'No Action - Dispute Rejected'),
    ]
    
    resolution_type = forms.ChoiceField(
        label=_('Resolution type'),
        choices=RESOLUTION_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        help_text=_('Select how to resolve this dispute'),
    )
    
    refund_amount = forms.DecimalField(
        label=_('Refund amount (if applicable)'),
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        validators=[MinValueValidator(0)],
        help_text=_('Amount to refund to client (for partial refunds)'),
    )
    
    refund_percentage = forms.IntegerField(
        label=_('Refund percentage (if applicable)'),
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'type': 'range',
            'min': '0',
            'max': '100',
            'step': '5',
        }),
        validators=[MinValueValidator(0)],
        help_text=_('Percentage to refund (for split payments)'),
    )
    
    notes = forms.CharField(
        label=_('Resolution notes'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Explain your resolution decision...',
        }),
        required=True,
        max_length=2000,
        help_text=_('These notes will be visible to both client and writer'),
    )
    
    notify_parties = forms.BooleanField(
        label=_('Notify client and writer'),
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Send email notifications about the resolution'),
    )
    
    penalize_writer = forms.BooleanField(
        label=_('Apply penalty to writer rating'),
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Reduce writer\'s rating if they were at fault'),
    )
    
    penalty_severity = forms.ChoiceField(
        label=_('Penalty severity (if applicable)'),
        choices=[
            ('minor', 'Minor - Small rating reduction'),
            ('moderate', 'Moderate - Rating reduction + warning'),
            ('severe', 'Severe - Rating reduction + temporary suspension'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text=_('How severe is the penalty for the writer?'),
    )
    
    def clean(self):
        """Validate dispute resolution form."""
        cleaned_data = super().clean()
        resolution_type = cleaned_data.get('resolution_type')
        
        # Validate refund amount for partial refunds
        if resolution_type == 'partial_refund':
            refund_amount = cleaned_data.get('refund_amount')
            if not refund_amount or refund_amount <= 0:
                raise forms.ValidationError({
                    'refund_amount': _('Refund amount is required for partial refunds.')
                })
        
        # Validate refund percentage for split payments
        if resolution_type == 'split_payment':
            refund_percentage = cleaned_data.get('refund_percentage')
            if not refund_percentage or refund_percentage < 0 or refund_percentage > 100:
                raise forms.ValidationError({
                    'refund_percentage': _('Valid refund percentage (0-100) is required for split payments.')
                })
        
        # Validate penalty severity if penalizing writer
        penalize_writer = cleaned_data.get('penalize_writer')
        if penalize_writer and not cleaned_data.get('penalty_severity'):
            raise forms.ValidationError({
                'penalty_severity': _('Penalty severity is required when penalizing writer.')
            })
        
        return cleaned_data


class OrderSearchForm(forms.Form):
    """Form for searching orders in admin."""
    
    SEARCH_FIELDS = [
        ('order_number', 'Order Number'),
        ('title', 'Order Title'),
        ('client_email', 'Client Email'),
        ('writer_email', 'Writer Email'),
        ('description', 'Order Description'),
    ]
    
    search_field = forms.ChoiceField(
        label=_('Search in'),
        choices=SEARCH_FIELDS,
        initial='order_number',
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    
    search_query = forms.CharField(
        label=_('Search query'),
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Enter search term...',
        }),
    )
    
    exact_match = forms.BooleanField(
        label=_('Exact match'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Match exact phrase instead of partial matches'),
    )
    
    case_sensitive = forms.BooleanField(
        label=_('Case sensitive'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Match case exactly'),
    )