from django import forms
from django.core.validators import MinValueValidator
from decimal import Decimal
import json

from .models import PayoutRequest


class PayoutRequestForm(forms.ModelForm):
    """Form for requesting payout"""
    
    class Meta:
        model = PayoutRequest
        fields = ['amount', 'payout_method', 'payout_details']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'payout_method': forms.Select(attrs={'class': 'form-control'}),
            'payout_details': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter payment details (e.g., PayPal email, bank account info)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.wallet = kwargs.pop('wallet', None)
        super().__init__(*args, **kwargs)
        
        if self.wallet:
            self.fields['amount'].validators.append(
                MinValueValidator(self.wallet.minimum_payout_threshold)
            )
            self.fields['amount'].widget.attrs['max'] = str(self.wallet.balance)
    
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        
        if self.wallet:
            if amount > self.wallet.balance:
                raise forms.ValidationError(
                    f"Amount exceeds available balance (${self.wallet.balance})"
                )
            
            if amount < self.wallet.minimum_payout_threshold:
                raise forms.ValidationError(
                    f"Minimum payout amount is ${self.wallet.minimum_payout_threshold}"
                )
        
        return amount
    
    def clean_payout_details(self):
        details = self.cleaned_data['payout_details']
        
        # Try to parse as JSON if it looks like JSON
        if details and (details.startswith('{') or details.startswith('[')):
            try:
                json.loads(details)
            except json.JSONDecodeError:
                # If not valid JSON, store as plain text
                pass
        
        return details


class WalletSettingsForm(forms.Form):
    """Form for wallet settings"""
    default_payment_method = forms.ChoiceField(
        choices=[
            ('', 'Select payment method'),
            ('paypal', 'PayPal'),
            ('bank_transfer', 'Bank Transfer'),
            ('skrill', 'Skrill'),
            ('payoneer', 'Payoneer'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    email_notifications = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Receive email notifications for transactions'
    )
    
    def __init__(self, *args, **kwargs):
        self.wallet = kwargs.pop('wallet', None)
        super().__init__(*args, **kwargs)
        
        if self.wallet:
            self.fields['default_payment_method'].initial = self.wallet.default_payment_method