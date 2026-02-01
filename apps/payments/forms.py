# apps/payments/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.conf import settings
from decimal import Decimal
import datetime
from django.db import models
from apps.payments.models import Payment, Refund
from apps.wallet.models import Wallet, PayoutRequest


class PaymentForm(forms.ModelForm):
    """Form for processing payments."""
    
    class Meta:
        model = Payment
        fields = ['payment_method']
        widgets = {
            'payment_method': forms.RadioSelect(attrs={
                'class': 'form-check-input',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
        
        # Dynamically set payment method choices based on available gateways
        available_methods = []
        
        # Always include wallet if user has one
        if self.request and hasattr(self.request.user, 'wallet'):
            available_methods.append(('wallet', _('Wallet Balance')))
        
        # Add Stripe if configured
        if hasattr(settings, 'STRIPE_PUBLIC_KEY') and settings.STRIPE_PUBLIC_KEY:
            available_methods.append(('stripe', _('Credit/Debit Card (Stripe)')))
        
        # Add PayPal if configured
        if hasattr(settings, 'PAYPAL_CLIENT_ID') and settings.PAYPAL_CLIENT_ID:
            available_methods.append(('paypal', _('PayPal')))
        
        # Add bank transfer if enabled
        if getattr(settings, 'ALLOW_BANK_TRANSFER', False):
            available_methods.append(('bank_transfer', _('Bank Transfer')))
        
        self.fields['payment_method'].choices = available_methods
        
        # Add custom validation for wallet payments
        if self.request and self.order:
            wallet = getattr(self.request.user, 'wallet', None)
            if wallet:
                if wallet.balance < self.order.total_price:
                    self.fields['payment_method'].widget.attrs['disabled'] = True
                    self.fields['payment_method'].help_text = _(
                        'Insufficient wallet balance. Please use another payment method.'
                    )
    
    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        
        if self.request and self.order:
            # Validate wallet balance for wallet payments
            if payment_method == 'wallet':
                wallet = getattr(self.request.user, 'wallet', None)
                if not wallet:
                    raise forms.ValidationError(_('No wallet found for your account.'))
                
                if wallet.balance < self.order.total_price:
                    raise forms.ValidationError(_(
                        'Insufficient wallet balance. Your balance is %(balance)s, '
                        'but the order total is %(total)s.'
                    ) % {
                        'balance': wallet.balance,
                        'total': self.order.total_price
                    })
            
            # Check if order already has a payment
            if hasattr(self.order, 'payment'):
                raise forms.ValidationError(_('This order already has a payment.'))
        
        return cleaned_data


class RefundRequestForm(forms.ModelForm):
    """Form for requesting refunds."""
    
    # Custom field for amount in partial refunds
    custom_amount = forms.DecimalField(
        label=_('Refund Amount'),
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter refund amount',
        })
    )
    
    class Meta:
        model = Refund
        fields = ['refund_type', 'refund_reason', 'custom_reason']
        widgets = {
            'refund_type': forms.RadioSelect(attrs={
                'class': 'form-check-input',
            }),
            'refund_reason': forms.Select(attrs={
                'class': 'form-select',
            }),
            'custom_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Please provide detailed explanation for your refund request...'),
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.payment = kwargs.pop('payment', None)
        self.order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
        
        # Set initial values
        if self.payment:
            self.fields['custom_amount'].widget.attrs['max'] = self.payment.amount
        
        # Show/hide custom amount field based on refund type
        self.fields['refund_type'].widget.attrs['onchange'] = 'toggleCustomAmount()'
        
        # Make custom_reason required for "other" reason
        if self.initial.get('refund_reason') == 'other':
            self.fields['custom_reason'].required = True
    
    def clean(self):
        cleaned_data = super().clean()
        refund_type = cleaned_data.get('refund_type')
        custom_amount = cleaned_data.get('custom_amount')
        refund_reason = cleaned_data.get('refund_reason')
        
        if self.payment:
            # Validate amount for partial refunds
            if refund_type == 'partial':
                if not custom_amount:
                    raise forms.ValidationError({
                        'custom_amount': _('Please specify the refund amount for partial refunds.')
                    })
                
                if custom_amount > self.payment.amount:
                    raise forms.ValidationError({
                        'custom_amount': _('Refund amount cannot exceed original payment amount.')
                    })
                
                # Check minimum partial refund amount
                min_partial_refund = getattr(settings, 'MIN_PARTIAL_REFUND_AMOUNT', Decimal('10.00'))
                if custom_amount < min_partial_refund:
                    raise forms.ValidationError({
                        'custom_amount': _('Minimum partial refund amount is %(amount)s.') % {
                            'amount': min_partial_refund
                        }
                    })
                
                cleaned_data['amount'] = custom_amount
            else:
                # Full refund uses full amount
                cleaned_data['amount'] = self.payment.amount
            
            # Validate custom_reason for "other" reason
            if refund_reason == 'other' and not cleaned_data.get('custom_reason'):
                raise forms.ValidationError({
                    'custom_reason': _('Please provide a detailed explanation for your refund request.')
                })
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set amount from cleaned data
        if 'amount' in self.cleaned_data:
            instance.amount = self.cleaned_data['amount']
        
        if commit:
            instance.save()
        
        return instance


class WithdrawalForm(forms.Form):
    """Form for withdrawing funds from wallet."""
    
    PAYMENT_METHOD_CHOICES = [
        ('paypal', _('PayPal')),
        ('bank_transfer', _('Bank Transfer')),
        ('skrill', _('Skrill')),
        ('payoneer', _('Payoneer')),
    ]
    
    amount = forms.DecimalField(
        label=_('Withdrawal Amount'),
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter amount to withdraw',
        }),
        help_text=_('Minimum withdrawal amount: %(min_amount)s') % {
            'min_amount': getattr(settings, 'MINIMUM_WITHDRAWAL_AMOUNT', '50.00')
        }
    )
    
    payment_method = forms.ChoiceField(
        label=_('Payment Method'),
        choices=PAYMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    account_details = forms.CharField(
        label=_('Account Details'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Enter your account email/ID for the selected payment method...'),
        }),
        help_text=_('For PayPal: enter your PayPal email. For bank transfer: enter your account details.')
    )
    
    terms_accepted = forms.BooleanField(
        label=_('I agree to the terms and conditions'),
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            # Get user's wallet
            try:
                wallet = Wallet.objects.get(user=self.user)
                # Set max value for amount field
                self.fields['amount'].widget.attrs['max'] = wallet.balance
                self.fields['amount'].help_text += _(' | Available balance: %(balance)s') % {
                    'balance': wallet.balance
                }
                
                # Dynamically set payment method choices based on user settings
                user_methods = getattr(self.user, 'payment_methods', [])
                if user_methods:
                    available_choices = [
                        (method, label) for method, label in self.PAYMENT_METHOD_CHOICES
                        if method in user_methods
                    ]
                    if available_choices:
                        self.fields['payment_method'].choices = available_choices
                
            except Wallet.DoesNotExist:
                pass
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        
        if self.user:
            try:
                wallet = Wallet.objects.get(user=self.user)
                
                # Check minimum withdrawal amount
                min_withdrawal = getattr(settings, 'MINIMUM_WITHDRAWAL_AMOUNT', Decimal('50.00'))
                if amount < min_withdrawal:
                    raise forms.ValidationError(
                        _('Minimum withdrawal amount is %(min_amount)s.') % {
                            'min_amount': min_withdrawal
                        }
                    )
                
                # Check wallet balance
                if amount > wallet.balance:
                    raise forms.ValidationError(
                        _('Insufficient balance. Available: %(balance)s') % {
                            'balance': wallet.balance
                        }
                    )
                
                # Check daily withdrawal limit
                today_start = datetime.datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                today_withdrawals = PayoutRequest.objects.filter(
                    wallet=wallet,
                    created_at__gte=today_start,
                    status='pending'
                ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
                
                daily_limit = getattr(settings, 'DAILY_WITHDRAWAL_LIMIT', Decimal('1000.00'))
                if today_withdrawals + amount > daily_limit:
                    raise forms.ValidationError(
                        _('Daily withdrawal limit exceeded. Today\'s withdrawals: %(today)s | Limit: %(limit)s') % {
                            'today': today_withdrawals,
                            'limit': daily_limit
                        }
                    )
                
            except Wallet.DoesNotExist:
                raise forms.ValidationError(_('No wallet found for your account.'))
        
        return amount
    
    def clean_account_details(self):
        payment_method = self.cleaned_data.get('payment_method')
        account_details = self.cleaned_data.get('account_details')
        
        # Validate account details based on payment method
        if payment_method == 'paypal':
            if '@' not in account_details or '.' not in account_details:
                raise forms.ValidationError(_('Please enter a valid PayPal email address.'))
        
        elif payment_method == 'bank_transfer':
            # Basic validation for bank details
            if len(account_details.strip()) < 10:
                raise forms.ValidationError(
                    _('Please provide complete bank account details including account number and bank name.')
                )
        
        return account_details


class AdminRefundForm(forms.ModelForm):
    """Form for admin to process refunds."""
    
    action = forms.ChoiceField(
        label=_('Action'),
        choices=[
            ('approve', _('Approve Refund')),
            ('reject', _('Reject Refund')),
            ('process', _('Process Approved Refund')),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
        })
    )
    
    review_notes = forms.CharField(
        label=_('Review Notes'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Enter notes about your decision...'),
        }),
        help_text=_('Required for approval/rejection')
    )
    
    rejection_reason = forms.CharField(
        label=_('Rejection Reason'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Explain why the refund is being rejected...'),
        }),
        help_text=_('Required when rejecting a refund')
    )
    
    auto_process = forms.BooleanField(
        label=_('Process refund automatically'),
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        help_text=_('Immediately process the refund through payment gateway when approved')
    )
    
    class Meta:
        model = Refund
        fields = []  # No model fields needed, using custom fields
    
    def __init__(self, *args, **kwargs):
        self.refund = kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)
        
        # Set initial action based on current state
        if self.refund:
            if self.refund.state == 'requested':
                self.fields['action'].initial = 'approve'
            elif self.refund.state == 'approved':
                self.fields['action'].initial = 'process'
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        review_notes = cleaned_data.get('review_notes')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        # Validate required fields based on action
        if action == 'approve' and not review_notes:
            raise forms.ValidationError({
                'review_notes': _('Review notes are required when approving a refund.')
            })
        
        if action == 'reject':
            if not rejection_reason:
                raise forms.ValidationError({
                    'rejection_reason': _('Rejection reason is required when rejecting a refund.')
                })
        
        # Check if refund can be processed
        if action == 'process' and self.refund:
            if self.refund.state != 'approved':
                raise forms.ValidationError(
                    _('Only approved refunds can be processed.')
                )
            
            if not self.refund.can_be_processed:
                raise forms.ValidationError(
                    _('This refund cannot be processed. Payment is not in a valid state.')
                )
        
        return cleaned_data


class EscrowReleaseForm(forms.Form):
    """Form for admin to release escrow funds."""
    
    release_type = forms.ChoiceField(
        label=_('Release Type'),
        choices=[
            ('manual', _('Manual Release')),
            ('automatic', _('Schedule Automatic Release')),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
        }),
        initial='manual'
    )
    
    release_date = forms.DateTimeField(
        label=_('Release Date'),
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
        }),
        help_text=_('Schedule automatic release for a future date')
    )
    
    notes = forms.CharField(
        label=_('Release Notes'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Optional notes about this release...'),
        })
    )
    
    send_notification = forms.BooleanField(
        label=_('Send notification to writer'),
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.payment = kwargs.pop('payment', None)
        super().__init__(*args, **kwargs)
        
        if self.payment and self.payment.escrow_held_until:
            # Set initial release date to scheduled date
            self.fields['release_date'].initial = self.payment.escrow_held_until
    
    def clean(self):
        cleaned_data = super().clean()
        release_type = cleaned_data.get('release_type')
        release_date = cleaned_data.get('release_date')
        
        if release_type == 'automatic' and not release_date:
            raise forms.ValidationError({
                'release_date': _('Release date is required for automatic release.')
            })
        
        if release_date:
            if release_date < datetime.datetime.now():
                raise forms.ValidationError({
                    'release_date': _('Release date must be in the future.')
                })
            
            # Check if release date is within allowed range
            max_future_days = getattr(settings, 'MAX_ESCROW_HOLD_DAYS', 30)
            max_date = datetime.datetime.now() + datetime.timedelta(days=max_future_days)
            if release_date > max_date:
                raise forms.ValidationError({
                    'release_date': _('Release date cannot be more than %(days)s days in the future.') % {
                        'days': max_future_days
                    }
                })
        
        return cleaned_data


class PaymentFilterForm(forms.Form):
    """Form for filtering payments."""
    
    STATUS_CHOICES = [
        ('', _('All Statuses')),
        ('initiated', _('Initiated')),
        ('processing', _('Processing')),
        ('held_in_escrow', _('Held in Escrow')),
        ('released_to_wallet', _('Released')),
        ('refunded', _('Refunded')),
        ('failed', _('Failed')),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('', _('All Methods')),
        ('stripe', _('Stripe')),
        ('paypal', _('PayPal')),
        ('wallet', _('Wallet')),
        ('bank_transfer', _('Bank Transfer')),
    ]
    
    status = forms.ChoiceField(
        label=_('Status'),
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    payment_method = forms.ChoiceField(
        label=_('Payment Method'),
        choices=PAYMENT_METHOD_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    date_from = forms.DateField(
        label=_('From Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        })
    )
    
    date_to = forms.DateField(
        label=_('To Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        })
    )
    
    min_amount = forms.DecimalField(
        label=_('Minimum Amount'),
        required=False,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min amount',
        })
    )
    
    max_amount = forms.DecimalField(
        label=_('Maximum Amount'),
        required=False,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max amount',
        })
    )
    
    search = forms.CharField(
        label=_('Search'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search by reference, order ID, or user...'),
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        min_amount = cleaned_data.get('min_amount')
        max_amount = cleaned_data.get('max_amount')
        
        # Validate date range
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError({
                'date_from': _('"From date" cannot be after "To date".')
            })
        
        # Validate amount range
        if min_amount and max_amount and min_amount > max_amount:
            raise forms.ValidationError({
                'min_amount': _('Minimum amount cannot be greater than maximum amount.')
            })
        
        return cleaned_data


class WalletTransactionFilterForm(forms.Form):
    """Form for filtering wallet transactions."""
    
    TRANSACTION_TYPE_CHOICES = [
        ('', _('All Types')),
        ('deposit', _('Deposit')),
        ('withdrawal', _('Withdrawal')),
        ('order_payment', _('Order Payment')),
        ('refund', _('Refund')),
        ('commission', _('Commission')),
        ('bonus', _('Bonus')),
    ]
    
    STATUS_CHOICES = [
        ('', _('All Statuses')),
        ('pending', _('Pending')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
    ]
    
    transaction_type = forms.ChoiceField(
        label=_('Transaction Type'),
        choices=TRANSACTION_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    status = forms.ChoiceField(
        label=_('Status'),
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    date_from = forms.DateField(
        label=_('From Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        })
    )
    
    date_to = forms.DateField(
        label=_('To Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        })
    )
    
    min_amount = forms.DecimalField(
        label=_('Minimum Amount'),
        required=False,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min amount',
        })
    )
    
    max_amount = forms.DecimalField(
        label=_('Maximum Amount'),
        required=False,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max amount',
        })
    )
    
    search = forms.CharField(
        label=_('Search'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search by reference or description...'),
        })
    )


class PaymentSettingsForm(forms.Form):
    """Form for payment gateway settings (admin)."""
    
    # Stripe settings
    stripe_public_key = forms.CharField(
        label=_('Stripe Public Key'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'pk_live_...',
        })
    )
    
    stripe_secret_key = forms.CharField(
        label=_('Stripe Secret Key'),
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'sk_live_...',
        }),
        help_text=_('Leave empty to keep current value')
    )
    
    stripe_webhook_secret = forms.CharField(
        label=_('Stripe Webhook Secret'),
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
        }),
        help_text=_('Leave empty to keep current value')
    )
    
    # PayPal settings
    paypal_client_id = forms.CharField(
        label=_('PayPal Client ID'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
        })
    )
    
    paypal_secret = forms.CharField(
        label=_('PayPal Secret'),
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
        }),
        help_text=_('Leave empty to keep current value')
    )
    
    paypal_mode = forms.ChoiceField(
        label=_('PayPal Mode'),
        choices=[
            ('sandbox', _('Sandbox')),
            ('live', _('Live')),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
        })
    )
    
    # Platform fee settings
    platform_fee_percentage = forms.DecimalField(
        label=_('Platform Fee Percentage'),
        min_value=Decimal('0'),
        max_value=Decimal('100'),
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
        }),
        help_text=_('Percentage fee taken by platform from each payment')
    )
    
    # Escrow settings
    escrow_hold_period = forms.IntegerField(
        label=_('Escrow Hold Period (days)'),
        min_value=1,
        max_value=90,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
        }),
        help_text=_('Number of days to hold funds in escrow after order completion')
    )
    
    # Withdrawal settings
    minimum_withdrawal_amount = forms.DecimalField(
        label=_('Minimum Withdrawal Amount'),
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
        })
    )
    
    daily_withdrawal_limit = forms.DecimalField(
        label=_('Daily Withdrawal Limit'),
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
        })
    )
    
    withdrawal_processing_days = forms.IntegerField(
        label=_('Withdrawal Processing Days'),
        min_value=1,
        max_value=30,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
        }),
        help_text=_('Number of business days to process withdrawal requests')
    )
    
    # Currency settings
    default_currency = forms.ChoiceField(
        label=_('Default Currency'),
        choices=[
            ('USD', 'USD - US Dollar'),
            ('EUR', 'EUR - Euro'),
            ('GBP', 'GBP - British Pound'),
            ('CAD', 'CAD - Canadian Dollar'),
            ('AUD', 'AUD - Australian Dollar'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    # Fraud prevention
    enable_fraud_check = forms.BooleanField(
        label=_('Enable Fraud Check'),
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        })
    )
    
    fraud_check_threshold = forms.DecimalField(
        label=_('Fraud Check Threshold'),
        required=False,
        min_value=Decimal('0'),
        max_value=Decimal('100'),
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
        }),
        help_text=_('Risk score threshold for flagging payments (0-100)')
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set initial values from settings
        self.fields['stripe_public_key'].initial = getattr(settings, 'STRIPE_PUBLIC_KEY', '')
        self.fields['paypal_client_id'].initial = getattr(settings, 'PAYPAL_CLIENT_ID', '')
        self.fields['paypal_mode'].initial = getattr(settings, 'PAYPAL_MODE', 'sandbox')
        self.fields['platform_fee_percentage'].initial = getattr(settings, 'PLATFORM_FEE_PERCENTAGE', 20)
        self.fields['escrow_hold_period'].initial = getattr(settings, 'ESCROW_HOLD_PERIOD', 7)
        self.fields['minimum_withdrawal_amount'].initial = getattr(settings, 'MINIMUM_WITHDRAWAL_AMOUNT', 50.00)
        self.fields['daily_withdrawal_limit'].initial = getattr(settings, 'DAILY_WITHDRAWAL_LIMIT', 1000.00)
        self.fields['withdrawal_processing_days'].initial = getattr(settings, 'WITHDRAWAL_PROCESSING_DAYS', 3)
        self.fields['default_currency'].initial = getattr(settings, 'DEFAULT_CURRENCY', 'USD')
        self.fields['enable_fraud_check'].initial = getattr(settings, 'ENABLE_FRAUD_CHECK', False)
        self.fields['fraud_check_threshold'].initial = getattr(settings, 'FRAUD_CHECK_THRESHOLD', 70)