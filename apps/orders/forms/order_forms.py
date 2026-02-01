from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from apps.orders.models import Order


class OrderCreateForm(forms.ModelForm):
    """Form for creating new orders."""
    
    title = forms.CharField(
        label=_('Order title'),
        max_length=500,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Research Paper on Climate Change',
        }),
        help_text=_('Clear, descriptive title for your order'),
    )
    
    description = forms.CharField(
        label=_('Detailed instructions'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Provide detailed instructions, requirements, and any specific guidelines...',
        }),
        max_length=5000,
        help_text=_('Be as detailed as possible to ensure the writer understands your requirements'),
    )
    
    subject = forms.CharField(
        label=_('Subject area'),
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Computer Science, Business, Psychology',
        }),
        help_text=_('The academic or professional field this order belongs to'),
    )
    
    academic_level = forms.ChoiceField(
        label=_('Academic level'),
        choices=Order.AcademicLevel.choices,
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial=Order.AcademicLevel.UNDERGRADUATE,
        help_text=_('The educational level required for this work'),
    )
    
    pages = forms.IntegerField(
        label=_('Number of pages'),
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text=_('Approximate number of pages (275 words per page)'),
    )
    
    words = forms.IntegerField(
        label=_('Number of words'),
        initial=275,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        validators=[MinValueValidator(100), MaxValueValidator(50000)],
        help_text=_('Exact word count required'),
    )
    
    sources = forms.IntegerField(
        label=_('Number of sources'),
        initial=3,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_('Minimum number of academic sources required'),
    )
    
    formatting_style = forms.CharField(
        label=_('Formatting style'),
        max_length=50,
        initial='APA',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., APA, MLA, Chicago, Harvard',
        }),
        help_text=_('Required citation and formatting style'),
    )
    
    urgency = forms.ChoiceField(
        label=_('Urgency level'),
        choices=Order.UrgencyLevel.choices,
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial=Order.UrgencyLevel.STANDARD,
        help_text=_('How soon you need this completed'),
    )
    
    deadline = forms.DateTimeField(
        label=_('Deadline'),
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
        }),
        help_text=_('Final deadline for order completion'),
    )
    
    price = forms.DecimalField(
        label=_('Your budget (USD)'),
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        validators=[MinValueValidator(5)],
        help_text=_('The amount you are willing to pay for this order'),
    )
    
    agree_to_terms = forms.BooleanField(
        label=_('I agree to the Order Terms and Conditions'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('You must agree to the terms to create an order.')
        },
    )
    
    confirm_instructions = forms.BooleanField(
        label=_('I confirm the instructions are clear and complete'),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        error_messages={
            'required': _('Please confirm your instructions are complete.')
        },
    )
    
    class Meta:
        model = Order
        fields = [
            'title', 'description', 'subject', 'academic_level',
            'pages', 'words', 'sources', 'formatting_style',
            'urgency', 'deadline', 'price',
        ]
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Set minimum date for deadline (tomorrow)
        tomorrow = timezone.now() + timezone.timedelta(days=1)
        self.fields['deadline'].widget.attrs['min'] = tomorrow.strftime('%Y-%m-%dT%H:%M')
    
    def clean_deadline(self):
        """Validate deadline."""
        deadline = self.cleaned_data.get('deadline')
        
        if not deadline:
            raise forms.ValidationError(_('Deadline is required.'))
        
        # Check if deadline is in the future
        if deadline <= timezone.now():
            raise forms.ValidationError(
                _('Deadline must be in the future.')
            )
        
        # Check minimum deadline based on urgency
        urgency = self.cleaned_data.get('urgency', Order.UrgencyLevel.STANDARD)
        
        min_deadlines = {
            Order.UrgencyLevel.EMERGENCY: timezone.timedelta(hours=24),
            Order.UrgencyLevel.VERY_URGENT: timezone.timedelta(days=3),
            Order.UrgencyLevel.URGENT: timezone.timedelta(days=7),
            Order.UrgencyLevel.STANDARD: timezone.timedelta(days=14),
        }
        
        min_deadline = timezone.now() + min_deadlines.get(urgency, timezone.timedelta(days=14))
        
        if deadline < min_deadline:
            raise forms.ValidationError(
                _('Deadline is too soon for the selected urgency level. '
                  f'Minimum for {self.get_urgency_display(urgency)} is {min_deadline.strftime("%Y-%m-%d %H:%M")}.')
            )
        
        # Check maximum deadline (6 months)
        max_deadline = timezone.now() + timezone.timedelta(days=180)
        if deadline > max_deadline:
            raise forms.ValidationError(
                _('Deadline cannot be more than 6 months in the future.')
            )
        
        return deadline
    
    def clean_price(self):
        """Validate price based on order parameters."""
        price = self.cleaned_data.get('price')
        
        if price < 5:
            raise forms.ValidationError(
                _('Minimum order price is $5.')
            )
        
        # Calculate suggested minimum price
        words = self.cleaned_data.get('words', 0)
        academic_level = self.cleaned_data.get('academic_level')
        urgency = self.cleaned_data.get('urgency')
        
        if words and academic_level and urgency:
            # Base rate per word based on academic level
            base_rates = {
                'high_school': 0.05,
                'undergraduate': 0.08,
                'bachelors': 0.10,
                'masters': 0.15,
                'phd': 0.20,
                'professional': 0.25,
            }
            
            # Urgency multiplier
            urgency_multipliers = {
                'standard': 1.0,
                'urgent': 1.5,
                'very_urgent': 2.0,
                'emergency': 3.0,
            }
            
            base_rate = base_rates.get(academic_level, 0.08)
            multiplier = urgency_multipliers.get(urgency, 1.0)
            
            suggested_min = words * base_rate * multiplier
            
            if price < suggested_min * 0.5:  # Allow some flexibility
                raise forms.ValidationError(
                    _('Price seems too low for this order. '
                      f'Suggested minimum: ${suggested_min:.2f}. '
                      'Very low prices may not attract qualified writers.')
                )
            
            if price > suggested_min * 5:  # Prevent excessive pricing
                raise forms.ValidationError(
                    _('Price seems too high for this order. '
                      f'Suggested range: ${suggested_min:.2f} - ${suggested_min * 2:.2f}.')
                )
        
        return price
    
    def clean_words(self):
        """Validate word count."""
        words = self.cleaned_data.get('words')
        pages = self.cleaned_data.get('pages', 1)
        
        if words and pages:
            # Check if words match page count (approx 275 words per page)
            expected_words_min = (pages - 1) * 275 + 1
            expected_words_max = pages * 275 + 100  # Allow some flexibility
            
            if words < expected_words_min:
                raise forms.ValidationError(
                    f'Word count seems low for {pages} page(s). '
                    f'Expected at least {expected_words_min} words.'
                )
            
            if words > expected_words_max:
                raise forms.ValidationError(
                    f'Word count seems high for {pages} page(s). '
                    f'Expected around {pages * 275} words (±100).'
                )
        
        return words
    
    def get_urgency_display(self, urgency_code):
        """Get display name for urgency code."""
        for code, name in Order.UrgencyLevel.choices:
            if code == urgency_code:
                return name
        return urgency_code


class OrderUpdateForm(forms.ModelForm):
    """Form for updating existing orders (draft only)."""
    
    class Meta:
        model = Order
        fields = [
            'title', 'description', 'subject', 'academic_level',
            'pages', 'words', 'sources', 'formatting_style',
            'urgency', 'deadline', 'price',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'academic_level': forms.Select(attrs={'class': 'form-control'}),
            'pages': forms.NumberInput(attrs={'class': 'form-control'}),
            'words': forms.NumberInput(attrs={'class': 'form-control'}),
            'sources': forms.NumberInput(attrs={'class': 'form-control'}),
            'formatting_style': forms.TextInput(attrs={'class': 'form-control'}),
            'urgency': forms.Select(attrs={'class': 'form-control'}),
            'deadline': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set minimum date for deadline
        if self.instance and self.instance.deadline:
            min_date = max(
                timezone.now() + timezone.timedelta(hours=1),
                self.instance.deadline  # Don't allow moving deadline earlier
            )
        else:
            min_date = timezone.now() + timezone.timedelta(hours=1)
        
        self.fields['deadline'].widget.attrs['min'] = min_date.strftime('%Y-%m-%dT%H:%M')
    
    def clean(self):
        """Validate order update."""
        cleaned_data = super().clean()
        
        # Check if order is still in draft state
        if self.instance.state != 'draft':
            raise forms.ValidationError(
                _('Only draft orders can be updated.')
            )
        
        return cleaned_data


class OrderFilterForm(forms.Form):
    """Form for filtering orders."""
    
    STATE_CHOICES = [('', 'All States')] + list(Order.STATE_CHOICES)
    ACADEMIC_LEVEL_CHOICES = [('', 'All Levels')] + list(Order.AcademicLevel.choices)
    
    state = forms.ChoiceField(
        label=_('Order State'),
        choices=STATE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    
    academic_level = forms.ChoiceField(
        label=_('Academic Level'),
        choices=ACADEMIC_LEVEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    
    date_from = forms.DateField(
        label=_('From Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-sm',
            'type': 'date',
        }),
    )
    
    date_to = forms.DateField(
        label=_('To Date'),
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-sm',
            'type': 'date',
        }),
    )
    
    search = forms.CharField(
        label=_('Search'),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Search orders...',
        }),
        max_length=100,
    )

class RevisionRequestForm(forms.Form):
    revision_instructions = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Please provide detailed instructions for the revision...',
            'rows': 5
        }),
        label="Instructions",
        help_text="Specify exactly what needs to be changed."
    )
    
    # Optional: If you want to allow file uploads for reference
    attachment = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )