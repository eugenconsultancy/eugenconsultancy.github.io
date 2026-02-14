from django import forms
from .models import Comment


class CommentForm(forms.ModelForm):
    """
    Form for submitting comments
    """
    class Meta:
        model = Comment
        fields = ['name', 'email', 'website', 'content', 'can_use_as_testimonial']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Share your thoughts...'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your@email.com'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://yourwebsite.com (optional)'
            }),
            'can_use_as_testimonial': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['website'].required = False