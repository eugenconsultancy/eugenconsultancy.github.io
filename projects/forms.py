from django import forms
from media_portfolio.projects.models import Project, ProjectComment


class ProjectForm(forms.ModelForm):
    """
    Form for creating/editing projects
    """
    class Meta:
        model = Project
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'short_summary': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'problem_statement': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'solution': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'technical_stack': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': '["Python", "Django", "React"]'
            }),
            'api_integrations': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': '["Stripe", "OpenAI"]'
            }),
            'tags': forms.TextInput(attrs={'class': 'form-control'}),
            'github_url': forms.URLInput(attrs={'class': 'form-control'}),
            'live_demo_url': forms.URLInput(attrs={'class': 'form-control'}),
            'documentation_url': forms.URLInput(attrs={'class': 'form-control'}),
            'difficulty_level': forms.Select(attrs={'class': 'form-select'}),
            'performance_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'published_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'license': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_technical_stack(self):
        """Validate technical stack is proper JSON"""
        data = self.cleaned_data.get('technical_stack')
        if isinstance(data, str):
            try:
                import json
                data = json.loads(data)
            except:
                raise forms.ValidationError("Invalid JSON format. Use: [\"Python\", \"Django\"]")
        return data

    def clean_api_integrations(self):
        """Validate API integrations is proper JSON"""
        data = self.cleaned_data.get('api_integrations')
        if isinstance(data, str):
            try:
                import json
                data = json.loads(data)
            except:
                raise forms.ValidationError("Invalid JSON format. Use: [\"Stripe\", \"OpenAI\"]")
        return data


class ProjectCommentForm(forms.ModelForm):
    """
    Form for submitting project comments
    """
    class Meta:
        model = ProjectComment
        fields = ['name', 'email', 'website', 'content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Share your thoughts about this project...'
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['website'].required = False


class ProjectFilterForm(forms.Form):
    """
    Form for filtering projects
    """
    difficulty = forms.ChoiceField(
        choices=[('', 'All Difficulties')] + Project.DIFFICULTY_LEVELS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    category = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search projects...'
        })
    )
    
    featured_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    sort = forms.ChoiceField(
        choices=[
            ('-published_date', 'Newest First'),
            ('published_date', 'Oldest First'),
            ('-stars_count', 'Most Stars'),
            ('-performance_score', 'Highest Performance'),
            ('title', 'Title A-Z'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )