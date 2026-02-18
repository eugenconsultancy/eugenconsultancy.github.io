from django import forms
from .models import Teacher
from accounts.models import User
from marks.models import Subject

class TeacherForm(forms.ModelForm):
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    
    teacher_role = forms.ChoiceField(
        choices=User.TEACHER_ROLE_CHOICES,
        required=True,
        initial='teacher'
    )
    
    class Meta:
        model = Teacher
        fields = [
            'username', 'email', 'first_name', 'last_name', 'password',
            'teacher_role', 'employee_id', 'department', 'subjects', 'classes',
            'assigned_subjects', 'qualification', 'experience', 'specialization',
            'extra_roles', 'extracurricular_activities',
            'phone', 'office_room'
        ]
        widgets = {
            'assigned_subjects': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'extra_roles': forms.Textarea(attrs={'rows': 3}),
            'extracurricular_activities': forms.Textarea(attrs={'rows': 3}),
        }
    
    def save(self, commit=True):
        # Create User first
        user_data = {
            'username': self.cleaned_data['username'],
            'email': self.cleaned_data['email'],
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'role': 'teacher',
            'teacher_role': self.cleaned_data['teacher_role'],
        }
        
        user = User.objects.create_user(
            username=user_data['username'],
            email=user_data['email'],
            password=self.cleaned_data['password'],
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            role='teacher',
            teacher_role=user_data['teacher_role']
        )
        
        # Create Teacher
        teacher = super().save(commit=False)
        teacher.user = user
        
        if commit:
            teacher.save()
            self.save_m2m()
        
        return teacher