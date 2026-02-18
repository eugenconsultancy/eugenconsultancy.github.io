from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from .models import Teacher
from accounts.models import User

class TeacherCreationForm(forms.ModelForm):
    """Form for creating teachers with user account creation"""
    username = forms.CharField(
        max_length=150, 
        required=True,
        help_text="Required. 150 characters or fewer."
    )
    email = forms.EmailField(
        required=True,
        help_text="Required. Teacher's email address."
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
        help_text="Enter a secure password for the teacher's account."
    )
    password2 = forms.CharField(
        label="Password confirmation",
        widget=forms.PasswordInput,
        help_text="Enter the same password as above, for verification."
    )
    
    class Meta:
        model = Teacher
        fields = '__all__'
        exclude = ('user',)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove user field from form as we'll create it programmatically
        if 'user' in self.fields:
            del self.fields['user']
    
    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with that username already exists.")
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email
    
    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        if Teacher.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError("A teacher with this employee ID already exists.")
        return employee_id
    
    def save(self, commit=True):
        # Create User first
        user_data = {
            'username': self.cleaned_data['username'],
            'email': self.cleaned_data['email'],
            'password': self.cleaned_data['password1'],
            'role': 'teacher',
            'is_active': True,
            'is_staff': True  # Teachers typically have staff access
        }
        
        user = User.objects.create_user(
            username=user_data['username'],
            email=user_data['email'],
            password=user_data['password'],
            role=user_data['role']
        )
        user.is_active = user_data['is_active']
        user.is_staff = user_data['is_staff']
        user.save()
        
        # Create Teacher with the user
        teacher = super().save(commit=False)
        teacher.user = user
        
        if commit:
            teacher.save()
            # Save many-to-many relationships if any
            self.save_m2m()
        
        return teacher

@admin.register(Teacher)
class TeacherAdmin(ModelAdmin):
    form = forms.ModelForm  # Use regular form for editing
    add_form = TeacherCreationForm  # Use custom form for adding
    
    list_display = ('employee_id', 'teacher_name', 'department', 'qualification', 'experience')
    list_filter = ('department', 'created_at')
    search_fields = ('employee_id', 'user__username', 'user__first_name', 'user__last_name', 'subjects', 'department')
    ordering = ('department', 'employee_id')
    readonly_fields = ('created_at', 'updated_at', 'teacher_user_info')
    filter_horizontal = ('assigned_subjects',)
    
    fieldsets = (
        (_('User Account'), {
            'fields': ('teacher_user_info',)
        }),
        (_('Employment Information'), {
            'fields': ('employee_id', 'department', 'qualification', 'experience', 'specialization'),
            'description': _('Professional information about the teacher.')
        }),
        (_('Teaching Information'), {
            'fields': ('subjects', 'classes', 'assigned_subjects'),
            'description': _('Subjects and classes taught by this teacher.')
        }),
        (_('Additional Roles'), {
            'fields': ('extra_roles', 'extracurricular_activities'),
            'description': _('Additional responsibilities and activities.')
        }),
        (_('Contact Information'), {
            'fields': ('phone', 'office_room')
        }),
        (_('Metadata'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (_('User Account Creation'), {
            'fields': ('username', 'email', 'password1', 'password2'),
            'description': _('Create a user account for the teacher first.')
        }),
        (_('Employment Information'), {
            'fields': ('employee_id', 'department', 'qualification', 'experience', 'specialization')
        }),
        (_('Teaching Information'), {
            'fields': ('subjects', 'classes', 'assigned_subjects')
        }),
        (_('Additional Roles'), {
            'fields': ('extra_roles', 'extracurricular_activities')
        }),
        (_('Contact Information'), {
            'fields': ('phone', 'office_room')
        }),
    )
    
    @admin.display(description='Teacher Name')
    def teacher_name(self, obj):
        if obj.user:
            full_name = obj.user.get_full_name()
            if full_name:
                return format_html('<strong>{}</strong>', full_name)
            return format_html('<strong>{}</strong>', obj.user.username)
        return format_html('<span style="color: red;">No User</span>')
    
    @admin.display(description='User Account')
    def teacher_user_info(self, obj):
        if obj.user:
            status_color = 'green' if obj.user.is_active else 'red'
            status_text = 'Active' if obj.user.is_active else 'Inactive'
            staff_badge = '<span class="badge bg-info">Staff</span>' if obj.user.is_staff else ''
            
            return format_html(
                '<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; border: 1px solid #dee2e6;">'
                '<h4 style="margin-top: 0;">User Account Information</h4>'
                '<table style="width: 100%;">'
                '<tr><td style="width: 30%;"><strong>Username:</strong></td><td>{}</td></tr>'
                '<tr><td><strong>Email:</strong></td><td>{}</td></tr>'
                '<tr><td><strong>Role:</strong></td><td><span class="badge bg-primary">{}</span> {}</td></tr>'
                '<tr><td><strong>Status:</strong></td><td><span style="color: {};">● {}</span></td></tr>'
                '<tr><td><strong>Staff Access:</strong></td><td>{}</td></tr>'
                '<tr><td><strong>Last Login:</strong></td><td>{}</td></tr>'
                '</table>'
                '</div>',
                obj.user.username,
                obj.user.email if obj.user.email else '<em>Not set</em>',
                obj.user.get_role_display(),
                staff_badge,
                status_color,
                status_text,
                'Yes' if obj.user.is_staff else 'No',
                obj.user.last_login.strftime('%Y-%m-%d %H:%M') if obj.user.last_login else 'Never'
            )
        return format_html(
            '<div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; border: 1px solid #ffeaa7;">'
            '<strong style="color: #856404;">⚠ No user account linked!</strong><br>'
            'This teacher profile is not linked to any user account.'
            '</div>'
        )
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Use special form for adding, but not for changing.
        """
        defaults = {}
        if obj is None:  # Adding a new object
            defaults['form'] = self.add_form
        else:  # Editing an existing object
            defaults['form'] = self.form
        
        defaults.update(kwargs)
        return super().get_form(request, obj, **defaults)
    
    def get_fieldsets(self, request, obj=None):
        if obj is None:  # Adding new
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return self.readonly_fields + ('employee_id',)
        return self.readonly_fields
    
    def save_model(self, request, obj, form, change):
        """Handle saving of teacher model"""
        if not change:  # Creating new
            # Form already handles user creation
            pass
        super().save_model(request, obj, form, change)
    
    # Custom methods for teacher
    def get_subjects_list(self, obj):
        """Display subjects as list"""
        return obj.get_subjects_list()
    get_subjects_list.short_description = 'Subjects'
    
    def get_classes_list(self, obj):
        """Display classes as list"""
        return obj.get_classes_list()
    get_classes_list.short_description = 'Classes'
    
    list_per_page = 25
    date_hierarchy = 'created_at'
    empty_value_display = '---'
    
    # Add custom actions
    actions = ['activate_teachers', 'deactivate_teachers', 'grant_staff_access', 'revoke_staff_access']
    
    @admin.action(description='Activate selected teachers')
    def activate_teachers(self, request, queryset):
        activated = 0
        for teacher in queryset:
            if teacher.user:
                teacher.user.is_active = True
                teacher.user.save()
                activated += 1
        self.message_user(request, f'{activated} teachers were activated.')
    
    @admin.action(description='Deactivate selected teachers')
    def deactivate_teachers(self, request, queryset):
        deactivated = 0
        for teacher in queryset:
            if teacher.user:
                teacher.user.is_active = False
                teacher.user.save()
                deactivated += 1
        self.message_user(request, f'{deactivated} teachers were deactivated.')
    
    @admin.action(description='Grant staff access to selected teachers')
    def grant_staff_access(self, request, queryset):
        granted = 0
        for teacher in queryset:
            if teacher.user:
                teacher.user.is_staff = True
                teacher.user.save()
                granted += 1
        self.message_user(request, f'{granted} teachers were granted staff access.')
    
    @admin.action(description='Revoke staff access from selected teachers')
    def revoke_staff_access(self, request, queryset):
        revoked = 0
        for teacher in queryset:
            if teacher.user:
                teacher.user.is_staff = False
                teacher.user.save()
                revoked += 1
        self.message_user(request, f'{revoked} teachers had staff access revoked.')