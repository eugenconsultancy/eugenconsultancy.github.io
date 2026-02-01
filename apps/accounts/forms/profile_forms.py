from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.accounts.models import WriterProfile

User = get_user_model()


class ProfileUpdateForm(forms.ModelForm):
    """Form for updating user profile information."""
    
    first_name = forms.CharField(
        label=_('First name'),
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'John',
        }),
    )
    
    last_name = forms.CharField(
        label=_('Last name'),
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Doe',
        }),
    )
    
    phone_number = forms.CharField(
        label=_('Phone number'),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1234567890',
        }),
        help_text=_('International format with country code'),
    )
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone_number')
    
    def clean_phone_number(self):
        """Validate phone number format."""
        phone_number = self.cleaned_data.get('phone_number', '').strip()
        
        if not phone_number:
            return phone_number
        
        # Basic phone number validation
        if not phone_number.startswith('+'):
            raise forms.ValidationError(
                _('Phone number must start with + and country code.')
            )
        
        # Remove non-digit characters for length check
        digits = ''.join(filter(str.isdigit, phone_number[1:]))
        
        if len(digits) < 10:
            raise forms.ValidationError(
                _('Phone number must have at least 10 digits.')
            )
        
        if len(digits) > 15:
            raise forms.ValidationError(
                _('Phone number is too long.')
            )
        
        return phone_number


class WriterProfileForm(forms.ModelForm):
    """Form for updating writer profile information."""
    
    bio = forms.CharField(
        label=_('Biography'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Tell us about your academic background and writing experience...',
        }),
        required=False,
        max_length=2000,
        help_text=_('Maximum 2000 characters'),
    )
    
    education_level = forms.ChoiceField(
        label=_('Highest education level'),
        choices=WriterProfile.EducationLevel.choices,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False,
    )
    
    institution = forms.CharField(
        label=_('Institution'),
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'University of Oxford',
        }),
    )
    
    graduation_year = forms.IntegerField(
        label=_('Graduation year'),
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '2020',
        }),
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
    )
    
    years_of_experience = forms.IntegerField(
        label=_('Years of experience'),
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '5',
        }),
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        help_text=_('Years of academic writing experience'),
    )
    
    hourly_rate = forms.DecimalField(
        label=_('Hourly rate'),
        max_digits=8,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '25.00',
        }),
        help_text=_('Your suggested hourly rate in USD'),
    )
    
    specialization = forms.CharField(
        label=_('Specialization'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'e.g., Computer Science, Business Management, Psychology',
        }),
        required=False,
        help_text=_('Comma-separated list of your areas of expertise'),
    )
    
    max_orders = forms.IntegerField(
        label=_('Maximum concurrent orders'),
        initial=3,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text=_('Maximum number of orders you can handle simultaneously'),
    )
    
    is_available = forms.BooleanField(
        label=_('Available for new assignments'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Uncheck if you\'re not currently accepting new work'),
    )
    
    class Meta:
        model = WriterProfile
        fields = [
            'bio', 'education_level', 'institution', 'graduation_year',
            'years_of_experience', 'hourly_rate', 'specialization',
            'max_orders', 'is_available',
        ]
    
    def clean_hourly_rate(self):
        """Validate hourly rate."""
        hourly_rate = self.cleaned_data.get('hourly_rate')
        
        if hourly_rate is not None and hourly_rate < 0:
            raise forms.ValidationError(
                _('Hourly rate cannot be negative.')
            )
        
        return hourly_rate
    
    def clean_specialization(self):
        """Clean and validate specialization field."""
        specialization = self.cleaned_data.get('specialization', '').strip()
        
        if specialization:
            # Split by comma and clean up
            specializations = [s.strip() for s in specialization.split(',')]
            specializations = [s for s in specializations if s]
            
            if len(specializations) > 20:
                raise forms.ValidationError(
                    _('Please limit to 20 specializations.')
                )
            
            # Join back with comma
            return ', '.join(specializations)
        
        return specialization


class AccountSettingsForm(forms.ModelForm):
    """Form for account settings."""
    
    email = forms.EmailField(
        label=_('Email address'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'you@example.com',
        }),
        help_text=_('Your primary email address for notifications'),
    )
    
    current_password = forms.CharField(
        label=_('Current password'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter current password to confirm changes',
        }),
        required=False,
        help_text=_('Required to change email address'),
    )
    
    class Meta:
        model = User
        fields = ('email',)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].initial = self.instance.email
    
    def clean_email(self):
        """Validate email change."""
        email = self.cleaned_data.get('email').lower()
        
        if email == self.instance.email:
            return email
        
        # Check if email is already taken
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(
                _('This email address is already in use.')
            )
        
        return email
    
    def clean(self):
        """Validate password for email change."""
        cleaned_data = super().clean()
        
        email = cleaned_data.get('email')
        current_password = cleaned_data.get('current_password')
        
        # If email is being changed, require current password
        if email and email != self.instance.email:
            if not current_password:
                raise forms.ValidationError({
                    'current_password': _('Current password is required to change email address.')
                })
            
            if not self.instance.check_password(current_password):
                raise forms.ValidationError({
                    'current_password': _('Current password is incorrect.')
                })
        
        return cleaned_data


class SecuritySettingsForm(forms.Form):
    """Form for security settings."""
    
    current_password = forms.CharField(
        label=_('Current password'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True,
    )
    
    new_password = forms.CharField(
        label=_('New password'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True,
    )
    
    confirm_password = forms.CharField(
        label=_('Confirm new password'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True,
    )
    
    def clean(self):
        """Validate password change."""
        cleaned_data = super().clean()
        
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError(
                _('New passwords do not match.')
            )
        
        return cleaned_data


class PrivacySettingsForm(forms.Form):
    """Form for privacy settings."""
    
    marketing_emails = forms.BooleanField(
        label=_('Receive marketing emails'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('News, promotions, and platform updates'),
    )
    
    data_processing_consent = forms.BooleanField(
        label=_('Data processing consent'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Required for using the platform'),
    )
    
    cookie_consent = forms.ChoiceField(
        label=_('Cookie preferences'),
        choices=[
            ('essential', 'Essential only'),
            ('analytics', 'Essential + Analytics'),
            ('all', 'All cookies'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='essential',
        help_text=_('Manage your cookie preferences'),
    )


class TwoFactorSetupForm(forms.Form):
    """Form for setting up two-factor authentication."""
    
    enable_2fa = forms.BooleanField(
        label=_('Enable two-factor authentication'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Add an extra layer of security to your account'),
    )
    
    phone_number = forms.CharField(
        label=_('Phone number for 2FA'),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1234567890',
        }),
        help_text=_('For receiving verification codes via SMS'),
    )
    
    backup_email = forms.EmailField(
        label=_('Backup email address'),
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'backup@example.com',
        }),
        help_text=_('For account recovery if you lose access'),
    )
    
    def clean(self):
        """Validate 2FA setup."""
        cleaned_data = super().clean()
        
        enable_2fa = cleaned_data.get('enable_2fa')
        phone_number = cleaned_data.get('phone_number')
        
        if enable_2fa and not phone_number:
            raise forms.ValidationError(
                _('Phone number is required when enabling two-factor authentication.')
            )
        
        return cleaned_data