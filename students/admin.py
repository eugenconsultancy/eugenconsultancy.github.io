from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from unfold.admin import ModelAdmin
from .models import Student
from accounts.models import User
from accounts.password_utils import generate_password

class StudentCreationForm(forms.ModelForm):
    """Form for creating students with automatic password generation"""
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    
    class Meta:
        model = Student
        fields = '__all__'
        exclude = ('user',)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'user' in self.fields:
            del self.fields['user']
    
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
    
    def clean_admission_number(self):
        admission_number = self.cleaned_data.get('admission_number')
        if Student.objects.filter(admission_number=admission_number).exists():
            raise forms.ValidationError("A student with this admission number already exists.")
        return admission_number
    
    def save(self, commit=True):
        # Generate password automatically
        password = generate_password(8)
        
        # Create User first
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data.get('email', ''),
            password=password,
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            role='student'
        )
        
        # Create Student with the user
        student = super().save(commit=False)
        student.user = user
        
        if commit:
            student.save()
        
        # Store generated password for display
        self.generated_password = password
        self.student_username = user.username
        
        return student

@admin.register(Student)
class StudentAdmin(ModelAdmin):
    form = forms.ModelForm
    add_form = StudentCreationForm
    
    list_display = ('admission_number', 'student_name', 'grade_section', 
                    'display_password', 'parent_name', 'date_of_birth', 'created_at')
    list_filter = ('grade', 'section', 'created_at')
    search_fields = ('admission_number', 'user__username', 'user__first_name', 
                     'user__last_name', 'parent_name')
    ordering = ('grade', 'section', 'admission_number')
    readonly_fields = ('created_at', 'updated_at', 'student_user_info')
    
    fieldsets = (
        (_('User Account'), {
            'fields': ('student_user_info',)
        }),
        (_('Academic Information'), {
            'fields': ('admission_number', 'grade', 'section', 'subjects'),
        }),
        (_('Personal Information'), {
            'fields': ('date_of_birth', 'address', 'phone'),
        }),
        (_('Parent Information'), {
            'fields': ('parent_name', 'parent_phone'),
        }),
        (_('Extracurricular Activities'), {
            'fields': ('clubs', 'societies'),
        }),
        (_('Metadata'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (_('User Account Creation'), {
            'fields': ('username', 'email', 'first_name', 'last_name'),
            'description': _('Student account will be created with auto-generated password.')
        }),
        (_('Academic Information (Required*)'), {
            'fields': ('admission_number', 'grade', 'section', 'subjects')
        }),
        (_('Personal Information (Required*)'), {
            'fields': ('date_of_birth', 'address', 'phone')
        }),
        (_('Parent Information (Required*)'), {
            'fields': ('parent_name', 'parent_phone')
        }),
        (_('Extracurricular Activities'), {
            'fields': ('clubs', 'societies')
        }),
    )
    
    @admin.display(description='Student Name')
    def student_name(self, obj):
        if obj.user:
            full_name = obj.user.get_full_name()
            if full_name:
                return format_html('<strong>{}</strong>', full_name)
            return format_html('<strong>{}</strong>', obj.user.username)
        return format_html('<span style="color: red;">No User</span>')
    
    @admin.display(description='Grade/Section')
    def grade_section(self, obj):
        return format_html('<span class="badge bg-primary">{}{}</span>', obj.grade, obj.section)
    
    @admin.display(description='Password')
    def display_password(self, obj):
        """Display password placeholder"""
        return format_html(
            '<span class="badge bg-secondary" title="Auto-generated 8-character password">'
            '<i class="fas fa-key"></i> Auto-generated</span>'
        )
    
    @admin.display(description='User Account')
    def student_user_info(self, obj):
        if obj.user:
            status_color = 'green' if obj.user.is_active else 'red'
            status_text = 'Active' if obj.user.is_active else 'Inactive'
            
            return format_html(
                '<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; border: 1px solid #dee2e6;">'
                '<h4 style="margin-top: 0;">User Account Information</h4>'
                '<table style="width: 100%;">'
                '<tr><td style="width: 30%;"><strong>Username:</strong></td><td>{}</td></tr>'
                '<tr><td><strong>Email:</strong></td><td>{}</td></tr>'
                '<tr><td><strong>Role:</strong></td><td><span class="badge bg-success">{}</span></td></tr>'
                '<tr><td><strong>Status:</strong></td><td><span style="color: {};">● {}</span></td></tr>'
                '<tr><td><strong>Last Login:</strong></td><td>{}</td></tr>'
                '</table>'
                '</div>',
                obj.user.username,
                obj.user.email if obj.user.email else '<em>Not set</em>',
                obj.user.get_role_display(),
                status_color,
                status_text,
                obj.user.last_login.strftime('%Y-%m-%d %H:%M') if obj.user.last_login else 'Never'
            )
        return format_html(
            '<div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; border: 1px solid #ffeaa7;">'
            '<strong style="color: #856404;">⚠ No user account linked!</strong><br>'
            'This student profile is not linked to any user account.'
            '</div>'
        )
    
    def get_form(self, request, obj=None, **kwargs):
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
            return self.readonly_fields + ('admission_number',)
        return self.readonly_fields
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new
            student = form.save(commit=False)
            
            # Display success message with password
            if hasattr(form, 'generated_password'):
                messages.success(
                    request, 
                    f'Student created successfully! Username: {form.student_username}, '
                    f'Password: <strong>{form.generated_password}</strong>'
                )
        
        super().save_model(request, obj, form, change)
    
    list_per_page = 25
    date_hierarchy = 'created_at'
    empty_value_display = '---'
    
    actions = ['activate_students', 'deactivate_students']
    
    @admin.action(description='Activate selected students')
    def activate_students(self, request, queryset):
        activated = 0
        for student in queryset:
            if student.user:
                student.user.is_active = True
                student.user.save()
                activated += 1
        self.message_user(request, f'{activated} students were activated.')
    
    @admin.action(description='Deactivate selected students')
    def deactivate_students(self, request, queryset):
        deactivated = 0
        for student in queryset:
            if student.user:
                student.user.is_active = False
                student.user.save()
                deactivated += 1
        self.message_user(request, f'{deactivated} students were deactivated.')