from django import forms
from .models import Category


class CategoryForm(forms.ModelForm):
    """
    Form for creating and editing categories
    """
    class Meta:
        model = Category
        fields = [
            'name', 'slug', 'category_type', 'parent', 'description',
            'cover_image', 'icon', 'meta_title', 'meta_description',
            'sort_order', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category name'
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'url-friendly-name'
            }),
            'category_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'parent': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe this category...'
            }),
            'cover_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'icon': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'fa-camera'
            }),
            'meta_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'SEO title (optional)'
            }),
            'meta_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'SEO description (optional)'
            }),
            'sort_order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make slug optional - will be auto-generated if not provided
        self.fields['slug'].required = False
        self.fields['slug'].help_text = "Leave blank to auto-generate from name"
        
        # Filter parent to only show categories of same type or no type restriction
        if self.instance and self.instance.pk:
            self.fields['parent'].queryset = Category.objects.filter(
                is_active=True
            ).exclude(pk=self.instance.pk)
        else:
            self.fields['parent'].queryset = Category.objects.filter(is_active=True)
        
        # Add help texts
        self.fields['icon'].help_text = "Font Awesome icon class (e.g., 'fa-camera', 'fa-video')"
        self.fields['category_type'].help_text = "Type of category for organization"
        self.fields['parent'].help_text = "Parent category (if this is a subcategory)"

    def clean_slug(self):
        """
        Ensure slug is unique
        """
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')
        
        if not slug and name:
            from django.utils.text import slugify
            slug = slugify(name)
        
        if slug:
            # Check uniqueness
            qs = Category.objects.filter(slug=slug)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError("This slug is already in use. Please choose another.")
        
        return slug

    def clean(self):
        """
        Additional validation
        """
        cleaned_data = super().clean()
        category_type = cleaned_data.get('category_type')
        parent = cleaned_data.get('parent')
        
        # Prevent circular parent relationships
        if parent and self.instance and self.instance.pk:
            if parent.pk == self.instance.pk:
                self.add_error('parent', "A category cannot be its own parent")
            
            # Check if parent is actually a child of this category (circular)
            current_parent = parent
            while current_parent:
                if current_parent == self.instance:
                    self.add_error('parent', "Cannot create circular parent relationship")
                    break
                current_parent = current_parent.parent
        
        return cleaned_data


class CategoryFilterForm(forms.Form):
    """
    Form for filtering categories in list views
    """
    type = forms.ChoiceField(
        choices=[('', 'All Types')] + Category.CATEGORY_TYPES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'onchange': 'this.form.submit()'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search categories...'
        })
    )
    
    active_only = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'onchange': 'this.form.submit()'
        })
    )


class CategoryBulkActionForm(forms.Form):
    """
    Form for bulk actions on categories (admin)
    """
    ACTION_CHOICES = [
        ('activate', 'Activate selected'),
        ('deactivate', 'Deactivate selected'),
        ('delete', 'Delete selected'),
        ('change_type', 'Change category type'),
        ('move_to_parent', 'Move to parent category'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    new_type = forms.ChoiceField(
        choices=Category.CATEGORY_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    new_parent = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        
        if action == 'change_type' and not cleaned_data.get('new_type'):
            self.add_error('new_type', 'New type is required for change type action')
        
        if action == 'move_to_parent' and not cleaned_data.get('new_parent'):
            self.add_error('new_parent', 'New parent is required for move action')
        
        return cleaned_data