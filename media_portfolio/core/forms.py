from django import forms
from .models import SiteSettings


class SiteSettingsForm(forms.ModelForm):
    """
    Form for editing site settings in admin
    """
    class Meta:
        model = SiteSettings
        fields = '__all__'
        widgets = {
            'site_description': forms.Textarea(attrs={'rows': 3}),
            'meta_keywords': forms.TextInput(attrs={'placeholder': 'comma, separated, keywords'}),
            'meta_description': forms.Textarea(attrs={'rows': 3}),
            'privacy_policy': forms.Textarea(attrs={'rows': 10}),
            'terms_of_service': forms.Textarea(attrs={'rows': 10}),
        }


class SearchForm(forms.Form):
    """
    Global search form
    """
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search...',
            'aria-label': 'Search'
        })
    )
    
    type = forms.ChoiceField(
        choices=[
            ('all', 'All'),
            ('image', 'Images'),
            ('video', 'Videos'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    category = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )