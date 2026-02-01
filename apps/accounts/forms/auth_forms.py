from django import forms
from django.contrib.auth.forms import (
    UserCreationForm, AuthenticationForm, 
    PasswordResetForm, SetPasswordForm
)
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.validators import validate_email
import re

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """Custom user creation form with email as username."""
    
    email = forms.EmailField(
        label=_('Email address'),
        max_length=254,
        widget=forms.EmailInput(attrs={
            'autocomplete': 'email',
            'class': 'form-control',
            'placeholder': 'you@example.com',
        }),
        help_text=_('Required. Enter a valid email address.')
    )
    
    password1 = forms.CharField(
        label=_('Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': 'form-control',
            'placeholder': 'Minimum 12 characters',
        }),
        help_text=_(
            'Your password must contain at least 12 characters, '
            'including uppercase, lowercase, numbers, and special characters.'
        ),
    )
    
    password2 = forms.CharField(
        label=_('Password confirmation'),
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': 'form-control',
            'placeholder': 'Confirm your password',
        }),
        strip=False,
        help_text=_('Enter the same password as before, for verification.'),
    )
    
    user_type = forms.ChoiceField(
        label=_('Account Type'),
        choices=User.UserType.choices,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial=User.UserType.CLIENT,
        help_text=_('Select the type of account you want to create.')
    )
    
    terms_accepted = forms.BooleanField(
        label=_('I accept the Terms of Service'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={'required': _('You must accept the terms to register.')},
    )
    
    privacy_policy_accepted = forms.BooleanField(
        label=_('I accept the Privacy Policy'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={'required': _('You must accept the privacy policy to register.')},
    )
    
    marketing_emails = forms.BooleanField(
        label=_('I want to receive marketing emails'),
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('You can change this preference anytime in your account settings.')
    )
    
    class Meta:
        model = User
        fields = ('email', 'password1', 'password2', 'user_type')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({'autofocus': True})
    
    def clean_email(self):
        """Validate email address."""
        email = self.cleaned_data.get('email').lower()
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                _('A user with this email address already exists.')
            )
        
        # Validate email format
        try:
            validate_email(email)
        except forms.ValidationError:
            raise forms.ValidationError(_('Enter a valid email address.'))
        
        # Check for disposable email addresses (basic check)
        disposable_domains = ['temp-mail.org', 'guerrillamail.com', 'mailinator.com']
        domain = email.split('@')[1]
        if any(disposable in domain for disposable in disposable_domains):
            raise forms.ValidationError(
                _('Disposable email addresses are not allowed.')
            )
        
        return email
    
    def clean_password1(self):
        """Validate password strength."""
        password1 = self.cleaned_data.get('password1')
        
        if len(password1) < 12:
            raise forms.ValidationError(
                _('Password must be at least 12 characters long.')
            )
        
        # Check for common password patterns
        if password1.lower() in ['password', '123456', 'qwerty', 'letmein']:
            raise forms.ValidationError(
                _('This password is too common. Please choose a stronger password.')
            )
        
        # Check for complexity
        if not re.search(r'[A-Z]', password1):
            raise forms.ValidationError(
                _('Password must contain at least one uppercase letter.')
            )
        
        if not re.search(r'[a-z]', password1):
            raise forms.ValidationError(
                _('Password must contain at least one lowercase letter.')
            )
        
        if not re.search(r'[0-9]', password1):
            raise forms.ValidationError(
                _('Password must contain at least one number.')
            )
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password1):
            raise forms.ValidationError(
                _('Password must contain at least one special character.')
            )
        
        # Check for sequential characters
        if re.search(r'(.)\1{2,}', password1):
            raise forms.ValidationError(
                _('Password contains too many repeated characters.')
            )
        
        return password1
    
    def save(self, commit=True):
        """Save the user with additional fields."""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email'].lower()
        user.user_type = self.cleaned_data['user_type']
        user.terms_accepted = self.cleaned_data['terms_accepted']
        user.privacy_policy_accepted = self.cleaned_data['privacy_policy_accepted']
        user.marketing_emails = self.cleaned_data['marketing_emails']
        
        if commit:
            user.save()
        
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """Custom authentication form with enhanced security."""
    
    username = forms.EmailField(
        label=_('Email address'),
        widget=forms.EmailInput(attrs={
            'autofocus': True,
            'class': 'form-control',
            'placeholder': 'you@example.com',
        })
    )
    
    password = forms.CharField(
        label=_('Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
        })
    )
    
    remember_me = forms.BooleanField(
        label=_('Remember me'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text=_('Stay logged in for 30 days')
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = _('Email')
    
    def clean_username(self):
        """Normalize email to lowercase."""
        username = self.cleaned_data.get('username')
        return username.lower() if username else username


class CustomPasswordResetForm(PasswordResetForm):
    """Custom password reset form with email validation."""
    
    email = forms.EmailField(
        label=_('Email address'),
        max_length=254,
        widget=forms.EmailInput(attrs={
            'autocomplete': 'email',
            'class': 'form-control',
            'placeholder': 'you@example.com',
        })
    )
    
    def clean_email(self):
        """Validate email and check if user exists."""
        email = self.cleaned_data['email'].lower()
        
        # Check if user exists
        if not User.objects.filter(email=email, is_active=True).exists():
            raise forms.ValidationError(
                _('No active account found with this email address.')
            )
        
        return email


class CustomSetPasswordForm(SetPasswordForm):
    """Custom set password form with enhanced validation."""
    
    new_password1 = forms.CharField(
        label=_('New password'),
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': 'form-control',
            'placeholder': 'Minimum 12 characters',
        }),
        strip=False,
        help_text=_(
            'Your password must contain at least 12 characters, '
            'including uppercase, lowercase, numbers, and special characters.'
        ),
    )
    
    new_password2 = forms.CharField(
        label=_('Confirm new password'),
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'new-password',
            'class': 'form-control',
            'placeholder': 'Confirm your new password',
        }),
        strip=False,
    )
    
    def clean_new_password1(self):
        """Validate new password strength."""
        password1 = self.cleaned_data.get('new_password1')
        
        # Reuse password validation from CustomUserCreationForm
        form = CustomUserCreationForm()
        form.cleaned_data = {'password1': password1}
        
        try:
            return form.clean_password1()
        except forms.ValidationError as e:
            raise forms.ValidationError(e.messages)
    
    def clean(self):
        """Additional validation."""
        cleaned_data = super().clean()
        
        # Check if new password is different from old password
        new_password = cleaned_data.get('new_password1')
        user = self.user
        
        if user.check_password(new_password):
            raise forms.ValidationError(
                _('New password must be different from your current password.')
            )
        
        return cleaned_data