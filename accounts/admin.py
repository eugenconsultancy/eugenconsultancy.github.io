from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from django.utils.html import format_html
from django.db import models
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.forms import UserCreationForm, UserChangeForm
from .models import User
from django.contrib.auth.models import Permission 

class CustomUserCreationForm(UserCreationForm):
    """A form for creating new users with password confirmation."""
    password1 = forms.CharField(
        label='Password', 
        widget=forms.PasswordInput(attrs={'class': 'vTextField'})
    )
    password2 = forms.CharField(
        label='Password confirmation', 
        widget=forms.PasswordInput(attrs={'class': 'vTextField'})
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'role', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set role to student by default for easier student creation
        if 'role' in self.fields:
            self.fields['role'].initial = 'student'
    
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

@admin.register(User)
class CustomUserAdmin(ModelAdmin):
    form = UserChangeForm
    add_form = CustomUserCreationForm
    
    list_display = ('username', 'email', 'first_name', 'last_name', 'role_display', 
                   'is_staff', 'is_active', 'last_login', 'date_joined')
    list_filter = ('role', 'is_staff', 'is_active', 'is_superuser', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    readonly_fields = ('last_login', 'date_joined', 'profile_picture_preview')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal Info'), {'fields': ('first_name', 'last_name', 'email', 'profile_picture', 'profile_picture_preview')}),
        (_('Role & Permissions'), {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important Dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role', 'profile_picture'),
        }),
        (_('Personal Info'), {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name'),
        }),
        (_('Permissions'), {
            'classes': ('wide',),
            'fields': ('is_active', 'is_staff', 'is_superuser'),
        }),
    )
    
    actions = ['activate_users', 'deactivate_users', 'make_staff', 'remove_staff', 'make_student', 'make_teacher']
    
    @admin.display(description='Role', ordering='role')
    def role_display(self, obj):
        role_colors = {
            'admin': 'red',
            'teacher': 'blue',
            'student': 'green',
            'parent': 'yellow',
        }
        color = role_colors.get(obj.role, 'gray')
        return format_html(
            '<span class="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset" style="color: {}; background-color: {}20;">{}</span>',
            color, color, obj.get_role_display()
        )
    
    @admin.display(description='Profile Picture')
    def profile_picture_preview(self, obj):
        if obj.profile_picture:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 100px; border-radius: 5px;" />',
                obj.profile_picture.url
            )
        return _("No picture")
    
    @admin.action(description='Activate selected users')
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users were successfully activated.')
    
    @admin.action(description='Deactivate selected users')
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users were successfully deactivated.')
    
    @admin.action(description='Make selected users staff')
    def make_staff(self, request, queryset):
        updated = queryset.update(is_staff=True)
        self.message_user(request, f'{updated} users were granted staff status.')
    
    @admin.action(description='Remove staff status from selected users')
    def remove_staff(self, request, queryset):
        updated = queryset.update(is_staff=False)
        self.message_user(request, f'{updated} users had staff status removed.')
    
    # NEW ACTION: Set selected users as students
    @admin.action(description='Set selected users as students')
    def make_student(self, request, queryset):
        updated = queryset.update(role='student')
        self.message_user(request, f'{updated} users were set as students.')
    
    # NEW ACTION: Set selected users as teachers
    @admin.action(description='Set selected users as teachers')
    def make_teacher(self, request, queryset):
        updated = queryset.update(role='teacher')
        self.message_user(request, f'{updated} users were set as teachers.')
    
    list_per_page = 25
    date_hierarchy = 'date_joined'
    empty_value_display = '---'

# Register Permission model
admin.site.register(Permission)