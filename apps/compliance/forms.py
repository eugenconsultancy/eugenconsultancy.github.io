# apps/compliance/forms.py
import uuid
from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.apps import apps


class DataRequestForm(forms.ModelForm):
    """Form for submitting GDPR data requests."""
    
    class Meta:
        model = None  # Will be set in __init__
        fields = ['request_type', 'description']
        widgets = {
            'request_type': forms.Select(attrs={
                'class': 'form-select',
                'placeholder': _('Select request type')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': _('Please describe your request in detail...')
            }),
        }
        labels = {
            'request_type': _('Type of Request'),
            'description': _('Request Details'),
        }
        help_texts = {
            'request_type': _('Select the type of GDPR request you are making'),
            'description': _('Provide as much detail as possible to help us process your request'),
        }
    
    def __init__(self, *args, user=None, **kwargs):
        # Get the model class dynamically
        DataRequest = apps.get_model('compliance', 'DataRequest')
        self._meta.model = DataRequest
        
        super().__init__(*args, **kwargs)
        self.user = user
        
        # Add request type descriptions
        self.request_type_descriptions = {
            'access': _('Request a copy of your personal data held by us'),
            'rectification': _('Request correction of inaccurate personal data'),
            'erasure': _('Request deletion of your personal data (right to be forgotten)'),
            'restriction': _('Request restriction of processing of your personal data'),
            'portability': _('Request your data in a machine-readable format'),
            'objection': _('Object to processing of your personal data'),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        request_type = cleaned_data.get('request_type')
        
        # Check for duplicate pending requests
        if self.user and request_type:
            DataRequest = apps.get_model('compliance', 'DataRequest')
            
            existing_request = DataRequest.objects.filter(
                user=self.user,
                request_type=request_type,
                status__in=['received', 'verifying', 'processing']
            ).exists()
            
            if existing_request:
                request_type_display = dict(DataRequest.RequestType.choices).get(request_type)
                raise forms.ValidationError(
                    _('You already have a pending %(type)s request. Please wait for it to be processed.'),
                    params={'type': request_type_display},
                    code='duplicate_request'
                )
        
        # Validate description length
        description = cleaned_data.get('description', '')
        if len(description.strip()) < 10:
            raise forms.ValidationError(
                _('Please provide more details in your request description (minimum 10 characters).'),
                code='description_too_short'
            )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to set the user."""
        instance = super().save(commit=False)
        instance.user = self.user
        
        if commit:
            instance.save()
        
        return instance


class ConsentWithdrawalForm(forms.Form):
    """Form for withdrawing consent."""
    
    consent_type = forms.ChoiceField(
        label=_('Consent Type'),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'consent-type-select'
        })
    )
    
    confirm = forms.BooleanField(
        label=_('I confirm I want to withdraw this consent'),
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'required': 'required'
        })
    )
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        
        # Get ConsentLog model dynamically
        ConsentLog = apps.get_model('compliance', 'ConsentLog')
        
        # Filter out required consents that cannot be withdrawn
        all_choices = ConsentLog.ConsentType.choices
        withdrawable_choices = []
        
        for choice_value, choice_label in all_choices:
            if self._is_withdrawable(choice_value):
                withdrawable_choices.append((choice_value, choice_label))
        
        self.fields['consent_type'].choices = withdrawable_choices
        
        if not withdrawable_choices:
            self.fields['consent_type'].widget.attrs['disabled'] = True
            self.fields['consent_type'].help_text = _('No withdrawable consents available')
    
    def _is_withdrawable(self, consent_type):
        """Check if a consent type can be withdrawn."""
        # Required consents that cannot be withdrawn
        non_withdrawable = ['registration', 'terms', 'privacy', 'data_processing']
        return consent_type not in non_withdrawable
    
    def clean_consent_type(self):
        consent_type = self.cleaned_data.get('consent_type')
        
        if not self._is_withdrawable(consent_type):
            raise forms.ValidationError(
                _('This consent type cannot be withdrawn as it is required for service operation.'),
                code='non_withdrawable'
            )
        
        return consent_type
    
    def clean(self):
        cleaned_data = super().clean()
        consent_type = cleaned_data.get('consent_type')
        confirm = cleaned_data.get('confirm')
        
        if consent_type and confirm and self.user:
            # Get ConsentLog model dynamically
            ConsentLog = apps.get_model('compliance', 'ConsentLog')
            
            # Verify user actually has this consent to withdraw
            has_given_consent = ConsentLog.objects.filter(
                user=self.user,
                consent_type=consent_type,
                consent_given=True
            ).exists()
            
            if not has_given_consent:
                raise forms.ValidationError(
                    _('You have not given consent for this type, so there is nothing to withdraw.'),
                    code='no_consent_to_withdraw'
                )
        
        return cleaned_data


class DataRequestVerificationForm(forms.Form):
    """Form for verifying data request identity."""
    
    verification_method = forms.ChoiceField(
        label=_('Verification Method'),
        choices=[
            ('email_confirmation', _('Email Confirmation')),
            ('id_document', _('ID Document Upload')),
            ('security_questions', _('Security Questions')),
            ('phone_verification', _('Phone Verification')),
            ('manual_review', _('Manual Review')),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )
    
    verification_notes = forms.CharField(
        label=_('Verification Notes'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Add any notes about the verification process...')
        }),
        help_text=_('Internal notes about how identity was verified')
    )
    
    additional_info = forms.CharField(
        label=_('Additional Information'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': _('Any additional information provided by the user...')
        })
    )


class DataRequestProcessingForm(forms.Form):
    """Form for processing data requests."""
    
    notes = forms.CharField(
        label=_('Processing Notes'),
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': _('Add notes about how the request is being processed...')
        }),
        help_text=_('These notes will be saved internally and help track the processing steps')
    )
    
    estimated_completion_date = forms.DateField(
        label=_('Estimated Completion Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'min': timezone.now().strftime('%Y-%m-%d'),
        }),
        help_text=_('When do you expect to complete this request?')
    )
    
    file_attachment = forms.FileField(
        label=_('Attach File'),
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.zip,.csv,.json'
        }),
        help_text=_('Attach exported data file (PDF, ZIP, CSV, JSON)')
    )
    
    def clean_estimated_completion_date(self):
        date = self.cleaned_data.get('estimated_completion_date')
        if date and date < timezone.now().date():
            raise forms.ValidationError(
                _('Estimated completion date cannot be in the past.'),
                code='invalid_date'
            )
        return date


class RetentionRuleForm(forms.ModelForm):
    """Form for creating/editing data retention rules."""
    
    class Meta:
        model = None  # Will be set in __init__
        fields = [
            'rule_name', 'data_type', 'retention_period_days',
            'action_type', 'is_active', 'description', 'legal_basis'
        ]
        widgets = {
            'rule_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., "User account anonymization after 2 years"')
            }),
            'data_type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'retention_period_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'step': 1,
                'placeholder': _('Days')
            }),
            'action_type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Describe what this rule does and why it exists...')
            }),
            'legal_basis': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('e.g., "GDPR Article 6(1)(f) - Legitimate interests"')
            }),
        }
        labels = {
            'rule_name': _('Rule Name'),
            'data_type': _('Data Type'),
            'retention_period_days': _('Retention Period (days)'),
            'action_type': _('Action Type'),
            'is_active': _('Active'),
            'description': _('Description'),
            'legal_basis': _('Legal Basis'),
        }
        help_texts = {
            'retention_period_days': _('Number of days to retain data before taking action'),
            'action_type': _('What action to take after retention period'),
            'legal_basis': _('GDPR article or other legal basis for this retention period'),
        }
    
    def __init__(self, *args, **kwargs):
        # Get model class dynamically BEFORE calling parent __init__
        DataRetentionRule = apps.get_model('compliance', 'DataRetentionRule')
        self._meta.model = DataRetentionRule
        
        super().__init__(*args, **kwargs)
        
        # Add validation for retention period
        self.fields['retention_period_days'].validators.append(MinValueValidator(1))
        
        # Add data type descriptions
        self.data_type_descriptions = {
            'user_account': _('User account information including profile data'),
            'order_data': _('Order history and transaction records'),
            'payment_data': _('Payment information and billing records'),
            'communication': _('Emails, messages, and other communications'),
            'logs': _('System and access logs'),
            'backups': _('Backup data and archives'),
        }
    
    def clean_rule_name(self):
        rule_name = self.cleaned_data.get('rule_name')
        
        # Get model class
        DataRetentionRule = apps.get_model('compliance', 'DataRetentionRule')
        
        # Check for duplicate rule names (excluding current instance)
        query = DataRetentionRule.objects.filter(rule_name=rule_name)
        if self.instance and self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        
        if query.exists():
            raise forms.ValidationError(
                _('A retention rule with this name already exists.'),
                code='duplicate_rule_name'
            )
        
        return rule_name
    
    def clean_retention_period_days(self):
        days = self.cleaned_data.get('retention_period_days')
        
        # Ensure retention period is reasonable
        if days > 3650:  # 10 years
            raise forms.ValidationError(
                _('Retention period cannot exceed 10 years (3650 days).'),
                code='retention_too_long'
            )
        
        return days


class ComplianceReportForm(forms.Form):
    """Form for generating compliance reports."""
    
    REPORT_TYPE_CHOICES = [
        ('daily', _('Daily Report')),
        ('weekly', _('Weekly Report')),
        ('monthly', _('Monthly Report')),
        ('quarterly', _('Quarterly Report')),
        ('yearly', _('Yearly Report')),
        ('custom', _('Custom Date Range')),
    ]
    
    EXPORT_FORMAT_CHOICES = [
        ('html', _('HTML (Web View)')),
        ('pdf', _('PDF Document')),
        ('csv', _('CSV Export')),
        ('json', _('JSON Data')),
    ]
    
    report_type = forms.ChoiceField(
        label=_('Report Type'),
        choices=REPORT_TYPE_CHOICES,
        initial='monthly',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'report-type-select'
        })
    )
    
    date_from = forms.DateField(
        label=_('From Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'id': 'date-from-input'
        })
    )
    
    date_to = forms.DateField(
        label=_('To Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'id': 'date-to-input'
        })
    )
    
    export_format = forms.ChoiceField(
        label=_('Export Format'),
        choices=EXPORT_FORMAT_CHOICES,
        initial='html',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    include_details = forms.BooleanField(
        label=_('Include Detailed Data'),
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text=_('Include detailed request and consent data in the report')
    )
    
    include_charts = forms.BooleanField(
        label=_('Include Charts and Graphs'),
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text=_('Include visual charts in HTML and PDF reports')
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default dates for monthly report
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        if not self.initial.get('date_from'):
            self.initial['date_from'] = month_start
        
        if not self.initial.get('date_to'):
            self.initial['date_to'] = today
    
    def clean(self):
        cleaned_data = super().clean()
        report_type = cleaned_data.get('report_type')
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if report_type == 'custom':
            if not date_from or not date_to:
                raise forms.ValidationError(
                    _('Both start and end dates are required for custom reports.'),
                    code='custom_dates_required'
                )
            
            if date_from > date_to:
                raise forms.ValidationError(
                    _('Start date cannot be after end date.'),
                    code='invalid_date_range'
                )
            
            # Validate date range is not too large
            delta = (date_to - date_from).days
            if delta > 366:  # More than 1 year
                raise forms.ValidationError(
                    _('Custom date range cannot exceed 1 year. Please use yearly report instead.'),
                    code='date_range_too_large'
                )
        
        return cleaned_data


# Additional forms for API and admin views
class AuditLogFilterForm(forms.Form):
    """Form for filtering audit logs."""
    
    ACTION_TYPE_CHOICES = [('', _('All Actions'))]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get AuditLog model dynamically
        AuditLog = apps.get_model('compliance', 'AuditLog')
        self.ACTION_TYPE_CHOICES += list(AuditLog.ActionType.choices)
        
        self.fields['action_type'] = forms.ChoiceField(
            label=_('Action Type'),
            choices=self.ACTION_TYPE_CHOICES,
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select'
            })
        )
    
    model_name = forms.CharField(
        label=_('Model Name'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('e.g., "User", "Order", "Payment"')
        })
    )
    
    object_id = forms.CharField(
        label=_('Object ID'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Specific object ID')
        })
    )
    
    date_from = forms.DateField(
        label=_('From Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        label=_('To Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )


class DataRequestFilterForm(forms.Form):
    """Form for filtering data requests (admin)."""
    
    STATUS_CHOICES = [('', _('All Statuses'))]
    TYPE_CHOICES = [('', _('All Types'))]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get DataRequest model dynamically
        DataRequest = apps.get_model('compliance', 'DataRequest')
        self.STATUS_CHOICES += list(DataRequest.RequestStatus.choices)
        self.TYPE_CHOICES += list(DataRequest.RequestType.choices)
        
        self.fields['status'] = forms.ChoiceField(
            label=_('Status'),
            choices=self.STATUS_CHOICES,
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select'
            })
        )
        
        self.fields['request_type'] = forms.ChoiceField(
            label=_('Request Type'),
            choices=self.TYPE_CHOICES,
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select'
            })
        )
    
    user = forms.ModelChoiceField(
        label=_('User'),
        queryset=get_user_model().objects.all(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    date_from = forms.DateField(
        label=_('Received From'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        label=_('Received To'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    overdue_only = forms.BooleanField(
        label=_('Show Overdue Only'),
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    urgent_only = forms.BooleanField(
        label=_('Show Urgent Only (≤7 days remaining)'),
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )


# Simple forms that don't need model imports
class BulkDataRequestActionForm(forms.Form):
    """Form for bulk actions on data requests."""
    
    ACTION_CHOICES = [
        ('verify', _('Verify Selected')),
        ('start_processing', _('Start Processing Selected')),
        ('mark_completed', _('Mark as Completed')),
        ('reject', _('Reject Selected')),
    ]
    
    action = forms.ChoiceField(
        label=_('Bulk Action'),
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    request_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    notes = forms.CharField(
        label=_('Action Notes'),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Add notes for this bulk action...')
        })
    )


class ConsentLogFilterForm(forms.Form):
    """Form for filtering consent logs."""
    
    CONSENT_TYPE_CHOICES = [('', _('All Types'))]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get ConsentLog model dynamically
        ConsentLog = apps.get_model('compliance', 'ConsentLog')
        self.CONSENT_TYPE_CHOICES += list(ConsentLog.ConsentType.choices)
        
        self.fields['consent_type'] = forms.ChoiceField(
            label=_('Consent Type'),
            choices=self.CONSENT_TYPE_CHOICES,
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select'
            })
        )
    
    consent_given = forms.ChoiceField(
        label=_('Consent Status'),
        choices=[
            ('', _('All Statuses')),
            ('true', _('Given')),
            ('false', _('Withdrawn'))
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    user = forms.ModelChoiceField(
        label=_('User'),
        queryset=get_user_model().objects.all(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    date_from = forms.DateField(
        label=_('From Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        label=_('To Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )