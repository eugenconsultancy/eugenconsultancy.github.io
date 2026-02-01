from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from ckeditor.widgets import CKEditorWidget
from taggit.forms import TagWidget

from .models import BlogPost, BlogComment, BlogCategory, BlogSubscription


class BlogPostForm(forms.ModelForm):
    """Form for creating/editing blog posts"""
    content = forms.CharField(widget=CKEditorWidget())
    
    class Meta:
        model = BlogPost
        fields = [
            'title', 'slug', 'excerpt', 'content', 'featured_image',
            'category', 'tags', 'meta_title', 'meta_description',
            'meta_keywords', 'canonical_url', 'status'
        ]
        widgets = {
            'tags': TagWidget(),
            'excerpt': forms.Textarea(attrs={'rows': 3}),
            'meta_description': forms.Textarea(attrs={'rows': 2}),
        }
        help_texts = {
            'title': 'Write a compelling title (50-60 characters recommended)',
            'excerpt': 'Brief summary for preview (150-160 characters recommended)',
            'meta_description': 'SEO description for search engines',
            'meta_keywords': 'Comma-separated keywords',
            'canonical_url': 'Original URL if this content is duplicated elsewhere',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make slug field not required initially
        self.fields['slug'].required = False
        
        # Limit category choices to active categories
        self.fields['category'].queryset = BlogCategory.objects.filter(is_active=True)
        
        # Add CSS classes
        for field_name, field in self.fields.items():
            if field_name not in ['content', 'tags']:
                field.widget.attrs.update({'class': 'form-control'})
    
    def clean_content(self):
        """Validate content length and quality"""
        content = self.cleaned_data['content']
        plain_text = strip_tags(content)
        word_count = len(plain_text.split())
        
        if word_count < 300:
            raise ValidationError(
                "Content must be at least 300 words. "
                f"Current word count: {word_count}"
            )
        
        return content
    
    def clean_excerpt(self):
        """Validate excerpt length"""
        excerpt = self.cleaned_data.get('excerpt', '')
        
        if excerpt and len(excerpt) > 300:
            raise ValidationError(
                "Excerpt should not exceed 300 characters."
            )
        
        return excerpt
    
    def clean_meta_description(self):
        """Validate meta description length"""
        meta_description = self.cleaned_data.get('meta_description', '')
        
        if meta_description and len(meta_description) > 300:
            raise ValidationError(
                "Meta description should not exceed 300 characters."
            )
        
        return meta_description
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        title = cleaned_data.get('title')
        content = cleaned_data.get('content')
        
        # Auto-generate slug from title if not provided
        if not cleaned_data.get('slug') and title:
            from django.utils.text import slugify
            cleaned_data['slug'] = slugify(title)[:220]
        
        # Auto-generate meta description from excerpt or content
        if not cleaned_data.get('meta_description'):
            excerpt = cleaned_data.get('excerpt', '')
            if excerpt:
                cleaned_data['meta_description'] = excerpt[:160]
            elif content:
                plain_text = strip_tags(content)[:160]
                cleaned_data['meta_description'] = plain_text
        
        # Auto-generate meta title from title
        if not cleaned_data.get('meta_title') and title:
            cleaned_data['meta_title'] = title[:200]
        
        return cleaned_data


class BlogCommentForm(forms.ModelForm):
    """Form for creating blog comments"""
    class Meta:
        model = BlogComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Add a comment...',
                'class': 'form-control'
            })
        }
    
    def clean_content(self):
        """Validate comment content"""
        content = self.cleaned_data['content']
        
        if len(content.strip()) < 10:
            raise ValidationError(
                "Comment must be at least 10 characters."
            )
        
        if len(content) > 1000:
            raise ValidationError(
                "Comment must not exceed 1000 characters."
            )
        
        return content


class SubscriptionForm(forms.ModelForm):
    """Form for blog subscription"""
    categories = forms.ModelMultipleChoiceField(
        queryset=BlogCategory.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Categories of interest"
    )
    
    class Meta:
        model = BlogSubscription
        fields = ['email', 'receive_new_posts', 'receive_weekly_digest', 'categories']
        widgets = {
            'email': forms.EmailInput(attrs={
                'placeholder': 'Your email address',
                'class': 'form-control'
            })
        }
        help_texts = {
            'receive_new_posts': 'Receive email notifications for new blog posts',
            'receive_weekly_digest': 'Receive weekly digest of popular posts',
        }
    
    def clean_email(self):
        """Validate email"""
        email = self.cleaned_data['email'].lower()
        
        # Check if already subscribed
        if BlogSubscription.objects.filter(
            email=email, 
            is_active=True
        ).exists():
            raise ValidationError(
                "This email is already subscribed to our newsletter."
            )
        
        return email


class BlogSearchForm(forms.Form):
    """Form for searching blog posts"""
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search blog posts...',
            'class': 'form-control'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=BlogCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    sort = forms.ChoiceField(
        choices=[
            ('newest', 'Newest First'),
            ('oldest', 'Oldest First'),
            ('popular', 'Most Popular'),
        ],
        required=False,
        initial='newest',
        widget=forms.Select(attrs={'class': 'form-control'})
    )