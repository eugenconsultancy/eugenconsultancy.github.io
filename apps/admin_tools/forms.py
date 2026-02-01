# apps/admin_tools/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
import json

from .models import (
    SystemHealthCheck, AdminTask, SystemConfiguration, 
    AdminNotificationPreference
)

User = get_user_model()


class AdminTaskForm(forms.ModelForm):
    """Form for creating/editing admin tasks"""
    
    class Meta:
        model = AdminTask
        fields = [
            'title', 'description', 'task_type', 'priority',
            'assigned_to', 'target_user', 'target_order',
            'due_date', 'estimated_hours', 'notes'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter task title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the task in detail'
            }),
            'task_type': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'target_user': forms.Select(attrs={'class': 'form-control'}),
            'target_order': forms.Select(attrs={'class': 'form-control'}),
            'due_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'estimated_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.5',
                'min': '0.5'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes'
            }),
        }
        help_texts = {
            'estimated_hours': 'Estimated time to complete the task',
            'due_date': 'When the task should be completed',
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter assigned_to to staff users only
        self.fields['assigned_to'].queryset = User.objects.filter(
            is_staff=True,
            is_active=True
        ).order_by('email')
        
        # Filter target_user to active users
        self.fields['target_user'].queryset = User.objects.filter(
            is_active=True
        ).order_by('email')
        
        # Make due date optional
        self.fields['due_date'].required = False
    
    def clean_due_date(self):
        """Validate due date is in the future"""
        due_date = self.cleaned_data.get('due_date')
        
        if due_date and due_date < timezone.now():
            raise ValidationError("Due date must be in the future")
        
        return due_date
    
    def clean_estimated_hours(self):
        """Validate estimated hours"""
        hours = self.cleaned_data.get('estimated_hours')
        
        if hours is not None and hours <= 0:
            raise ValidationError("Estimated hours must be greater than 0")
        
        return hours
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        
        # Validate that either target_user or target_order is provided for certain task types
        task_type = cleaned_data.get('task_type')
        target_user = cleaned_data.get('target_user')
        target_order = cleaned_data.get('target_order')
        
        if task_type in ['writer_review', 'user_management'] and not target_user:
            self.add_error('target_user', 'Target user is required for this task type')
        
        if task_type in ['order_assignment', 'dispute_resolution'] and not target_order:
            self.add_error('target_order', 'Target order is required for this task type')
        
        return cleaned_data


class TaskAssignmentForm(forms.Form):
    """Form for assigning tasks to admin users"""
    
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.filter(is_staff=True, is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Assign to",
        help_text="Select a staff member to assign this task to"
    )
    
    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add any notes for the assignee'
        }),
        required=False,
        label="Assignment Notes"
    )
    
    def __init__(self, *args, **kwargs):
        self.task = kwargs.pop('task', None)
        super().__init__(*args, **kwargs)
        
        if self.task and self.task.assigned_to:
            self.fields['assigned_to'].initial = self.task.assigned_to


class TaskCompletionForm(forms.Form):
    """Form for completing tasks"""
    
    result = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Describe the results of the task...'
        }),
        label="Task Results",
        help_text="Provide details about what was done and the outcome"
    )
    
    actual_hours = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.5',
            'min': '0.5'
        }),
        required=False,
        label="Actual Hours Spent",
        help_text="How many hours were actually spent on this task"
    )
    
    attachments = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
        }),
        required=False,
        label="Attachments",
        help_text="Upload any relevant files (max 10MB)"
    )
    
    def clean_actual_hours(self):
        """Validate actual hours"""
        hours = self.cleaned_data.get('actual_hours')
        
        if hours is not None and hours <= 0:
            raise ValidationError("Actual hours must be greater than 0 if provided")
        
        return hours
    
    def clean_attachments(self):
        """Validate attachment file size"""
        attachment = self.cleaned_data.get('attachments')
        
        if attachment:
            # Check file size (10MB limit)
            if attachment.size > 10 * 1024 * 1024:  # 10MB
                raise ValidationError("File size must be under 10MB")
            
            # Check file extension
            allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.xls', '.xlsx']
            if not any(attachment.name.lower().endswith(ext) for ext in allowed_extensions):
                raise ValidationError(
                    f"File type not allowed. Allowed types: {', '.join([ext.lstrip('.') for ext in allowed_extensions])}"
                )
        
        return attachment


class SystemConfigurationForm(forms.ModelForm):
    """Form for editing system configuration"""
    
    class Meta:
        model = SystemConfiguration
        fields = ['value_string', 'value_number', 'value_boolean', 'value_json']
        widgets = {
            'value_string': forms.TextInput(attrs={'class': 'form-control'}),
            'value_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'value_boolean': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'value_json': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Enter JSON data'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Show only the relevant field based on existing value
        if self.instance.value_string is not None and self.instance.value_string != '':
            self.fields['value_string'].initial = self.instance.value_string
            self.fields['value_number'].widget = forms.HiddenInput()
            self.fields['value_boolean'].widget = forms.HiddenInput()
            self.fields['value_json'].widget = forms.HiddenInput()
        elif self.instance.value_number is not None:
            self.fields['value_number'].initial = float(self.instance.value_number)
            self.fields['value_string'].widget = forms.HiddenInput()
            self.fields['value_boolean'].widget = forms.HiddenInput()
            self.fields['value_json'].widget = forms.HiddenInput()
        elif self.instance.value_boolean is not None:
            self.fields['value_boolean'].initial = self.instance.value_boolean
            self.fields['value_string'].widget = forms.HiddenInput()
            self.fields['value_number'].widget = forms.HiddenInput()
            self.fields['value_json'].widget = forms.HiddenInput()
        elif self.instance.value_json is not None:
            try:
                self.fields['value_json'].initial = json.dumps(self.instance.value_json, indent=2)
            except (TypeError, ValueError):
                self.fields['value_json'].initial = str(self.instance.value_json)
            self.fields['value_string'].widget = forms.HiddenInput()
            self.fields['value_number'].widget = forms.HiddenInput()
            self.fields['value_boolean'].widget = forms.HiddenInput()
    
    def clean_value_json(self):
        """Validate JSON field"""
        value = self.cleaned_data.get('value_json')
        
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format")
        
        return value


class BulkConfigurationForm(forms.Form):
    """Form for bulk updating system configurations"""
    
    configurations = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': 'Enter configurations as JSON:\n{\n  "key1": "value1",\n  "key2": 123,\n  "key3": true\n}'
        }),
        help_text="Enter configurations as a JSON object with key-value pairs"
    )
    
    def clean_configurations(self):
        """Validate JSON configurations"""
        config_text = self.cleaned_data.get('configurations')
        
        if not config_text:
            return {}
        
        try:
            configs = json.loads(config_text)
            if not isinstance(configs, dict):
                raise ValidationError("Configurations must be a JSON object")
            return configs
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {str(e)}")


class AdminNotificationPreferenceForm(forms.ModelForm):
    """Form for admin notification preferences"""
    
    class Meta:
        model = AdminNotificationPreference
        fields = [
            'email_writer_approvals', 'email_order_assignments', 'email_dispute_alerts',
            'email_refund_requests', 'email_system_alerts', 'email_compliance_issues',
            'inapp_writer_approvals', 'inapp_order_assignments', 'inapp_dispute_alerts',
            'inapp_refund_requests', 'inapp_system_alerts', 'inapp_compliance_issues',
            'digest_frequency', 'quiet_hours_start', 'quiet_hours_end'
        ]
        widgets = {
            'digest_frequency': forms.Select(attrs={'class': 'form-control'}),
            'quiet_hours_start': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'quiet_hours_end': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add CSS classes to boolean fields
        for field_name in self.fields:
            if isinstance(self.fields[field_name], forms.BooleanField):
                self.fields[field_name].widget.attrs.update({'class': 'form-check-input'})
    
    def clean(self):
        """Validate quiet hours"""
        cleaned_data = super().clean()
        start = cleaned_data.get('quiet_hours_start')
        end = cleaned_data.get('quiet_hours_end')
        
        if start and end and start == end:
            raise ValidationError("Quiet hours start and end times cannot be the same")
        
        return cleaned_data


class AuditLogFilterForm(forms.Form):
    """Form for filtering audit logs"""
    
    action_type = forms.ChoiceField(
        choices=[('', 'All Actions')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    admin_user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_staff=True, is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="All Admins"
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="From Date"
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="To Date"
    )
    
    target_user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Any User"
    )
    
    export_format = forms.ChoiceField(
        choices=[
            ('', 'Select Format'),
            ('json', 'JSON'),
            ('csv', 'CSV')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Export Format"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get task type choices from AdminTask model
        try:
            task_type_choices = [('', 'All Actions')] + list(AdminTask.TaskType.choices)
            self.fields['action_type'].choices = task_type_choices
        except AttributeError:
            # Fallback if TaskType choices not available
            self.fields['action_type'].choices = [
                ('', 'All Actions'),
                ('writer_review', 'Writer Review'),
                ('order_assignment', 'Order Assignment'),
                ('dispute_resolution', 'Dispute Resolution'),
                ('user_management', 'User Management'),
                ('system_maintenance', 'System Maintenance'),
            ]
    
    def clean(self):
        """Validate date range"""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date cannot be after end date")
        
        return cleaned_data


class HealthCheckFilterForm(forms.Form):
    """Form for filtering health checks"""
    
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="From Date"
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="To Date"
    )
    
    min_score = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '100'
        }),
        label="Minimum Score"
    )
    
    max_score = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '100'
        }),
        label="Maximum Score"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get health status choices from SystemHealthCheck model
        try:
            status_choices = [('', 'All Statuses')] + list(SystemHealthCheck.HealthStatus.choices)
            self.fields['status'].choices = status_choices
        except AttributeError:
            # Fallback if HealthStatus choices not available
            self.fields['status'].choices = [
                ('', 'All Statuses'),
                ('healthy', 'Healthy'),
                ('warning', 'Warning'),
                ('critical', 'Critical'),
            ]
    
    def clean(self):
        """Validate date and score ranges"""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        min_score = cleaned_data.get('min_score')
        max_score = cleaned_data.get('max_score')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date cannot be after end date")
        
        if min_score and max_score and min_score > max_score:
            raise ValidationError("Minimum score cannot be greater than maximum score")
        
        return cleaned_data


# Optional: Alternative TaskCompletionForm with multiple file support
class TaskCompletionFormMultipleFiles(forms.Form):
    """Form for completing tasks with multiple file uploads"""
    
    result = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Describe the results of the task...'
        }),
        label="Task Results",
        help_text="Provide details about what was done and the outcome"
    )
    
    actual_hours = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.5',
            'min': '0.5'
        }),
        required=False,
        label="Actual Hours Spent",
        help_text="How many hours were actually spent on this task"
    )
    
    attachments = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
        }),
        required=False,
        label="Attachments",
        help_text="Upload any relevant files (max 10MB)"
    )
    
    def clean_attachments(self):
        """Validate attachment file size"""
        attachment = self.cleaned_data.get('attachments')
        
        if attachment:
            # Check file size (10MB limit)
            if attachment.size > 10 * 1024 * 1024:  # 10MB
                raise ValidationError("File size must be under 10MB")
            
            # Check file extension
            allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.xls', '.xlsx']
            if not any(attachment.name.lower().endswith(ext) for ext in allowed_extensions):
                raise ValidationError(
                    f"File type not allowed. Allowed types: {', '.join([ext.lstrip('.') for ext in allowed_extensions])}"
                )
        
        return attachment