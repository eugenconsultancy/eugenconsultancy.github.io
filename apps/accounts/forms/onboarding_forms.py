from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.accounts.models import WriterProfile


class OnboardingStep1Form(forms.ModelForm):
    """Form for step 1 of writer onboarding (profile completion)."""
    
    first_name = forms.CharField(
        label=_('First name'),
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'John',
            'required': True,
        }),
    )
    
    last_name = forms.CharField(
        label=_('Last name'),
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Doe',
            'required': True,
        }),
    )
    
    phone_number = forms.CharField(
        label=_('Phone number'),
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1234567890',
            'required': True,
        }),
        help_text=_('International format with country code'),
    )
    
    country = forms.CharField(
        label=_('Country'),
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'United States',
            'required': True,
        }),
    )
    
    bio = forms.CharField(
        label=_('Professional biography'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Tell us about your academic background and writing experience...',
            'required': True,
        }),
        max_length=2000,
        help_text=_('Maximum 2000 characters. Describe your qualifications and experience.'),
    )
    
    education_level = forms.ChoiceField(
        label=_('Highest education level'),
        choices=WriterProfile.EducationLevel.choices,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': True,
        }),
        help_text=_('Select your highest completed education level'),
    )
    
    institution = forms.CharField(
        label=_('Educational institution'),
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'University of Oxford',
            'required': True,
        }),
        help_text=_('Name of your university or college'),
    )
    
    graduation_year = forms.IntegerField(
        label=_('Graduation year'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '2020',
            'required': True,
        }),
        validators=[MinValueValidator(1900), MaxValueValidator(2100)],
        help_text=_('Year you graduated or expect to graduate'),
    )
    
    years_of_experience = forms.IntegerField(
        label=_('Years of academic writing experience'),
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'required': True,
        }),
        validators=[MinValueValidator(0), MaxValueValidator(50)],
    )
    
    hourly_rate = forms.DecimalField(
        label=_('Suggested hourly rate (USD)'),
        max_digits=8,
        decimal_places=2,
        initial=25.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'required': True,
        }),
        help_text=_('You can adjust this later based on your experience'),
    )
    
    specialization = forms.CharField(
        label=_('Areas of specialization'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Computer Science, Business Management, Psychology, Literature',
            'required': True,
        }),
        help_text=_('Comma-separated list of your academic expertise areas'),
    )
    
    max_orders = forms.IntegerField(
        label=_('Maximum concurrent orders'),
        initial=3,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text=_('Maximum number of orders you can handle at once'),
    )
    
    is_available = forms.BooleanField(
        label=_('I am available to accept assignments'),
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        required=False,
    )
    
    class Meta:
        model = WriterProfile
        fields = [
            'bio', 'education_level', 'institution', 'graduation_year',
            'years_of_experience', 'hourly_rate', 'specialization',
            'max_orders', 'is_available',
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add user fields to form data if instance has user
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['phone_number'].initial = self.instance.user.phone_number
    
    def clean_hourly_rate(self):
        """Validate hourly rate."""
        hourly_rate = self.cleaned_data.get('hourly_rate')
        
        if hourly_rate < 5:
            raise forms.ValidationError(
                _('Hourly rate must be at least $5.')
            )
        
        if hourly_rate > 500:
            raise forms.ValidationError(
                _('Hourly rate cannot exceed $500.')
            )
        
        return hourly_rate
    
    def clean_graduation_year(self):
        """Validate graduation year."""
        graduation_year = self.cleaned_data.get('graduation_year')
        current_year = 2024  # Would use timezone.now().year in production
        
        if graduation_year > current_year + 5:
            raise forms.ValidationError(
                _('Graduation year cannot be more than 5 years in the future.')
            )
        
        return graduation_year
    
    def clean_specialization(self):
        """Validate specialization field."""
        specialization = self.cleaned_data.get('specialization', '').strip()
        
        if not specialization:
            raise forms.ValidationError(
                _('Please specify at least one area of specialization.')
            )
        
        # Split by comma and clean up
        specializations = [s.strip() for s in specialization.split(',')]
        specializations = [s for s in specializations if s]
        
        if len(specializations) < 1:
            raise forms.ValidationError(
                _('Please specify at least one area of specialization.')
            )
        
        if len(specializations) > 10:
            raise forms.ValidationError(
                _('Please limit to 10 specializations.')
            )
        
        # Validate each specialization length
        for spec in specializations:
            if len(spec) > 100:
                raise forms.ValidationError(
                    _('Each specialization should be under 100 characters.')
                )
        
        # Join back with comma
        return ', '.join(specializations)
    
    def save(self, commit=True):
        """Save writer profile and update user information."""
        writer_profile = super().save(commit=False)
        
        # Update user information
        user = writer_profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data['phone_number']
        
        if commit:
            user.save()
            writer_profile.save()
        
        return writer_profile


class OnboardingStep2Form(forms.Form):
    """Form for step 2 of writer onboarding (document submission confirmation)."""
    
    confirm_documents_authentic = forms.BooleanField(
        label=_('I confirm all uploaded documents are authentic and belong to me'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must confirm the authenticity of your documents.')
        },
    )
    
    agree_to_verification = forms.BooleanField(
        label=_('I agree to my documents being verified by EBWriting administrators'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must agree to document verification.')
        },
    )
    
    confirm_academic_integrity = forms.BooleanField(
        label=_('I will maintain academic integrity in all my work'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must agree to maintain academic integrity.')
        },
    )
    
    confirm_platform_rules = forms.BooleanField(
        label=_('I have read and agree to follow all platform rules and guidelines'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must agree to follow platform rules.')
        },
    )
    
    ready_for_review = forms.BooleanField(
        label=_('I am ready to submit my documents for admin review'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must confirm you are ready for review.')
        },
    )