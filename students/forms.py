from django import forms
from .models import Student
from accounts.models import User
from accounts.password_utils import generate_password

class StudentForm(forms.ModelForm):
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    
    # Remove password field since it's auto-generated
    # password = forms.CharField(widget=forms.PasswordInput, required=True)
    
    class Meta:
        model = Student
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'admission_number', 'grade', 'section', 'date_of_birth',
            'address', 'phone', 'parent_name', 'parent_phone',
            'clubs', 'societies', 'subjects'
        ]
    
    def save(self, commit=True):
        # Generate password automatically
        password = generate_password(8)
        
        # Create User first
        user_data = {
            'username': self.cleaned_data['username'],
            'email': self.cleaned_data.get('email', ''),
            'password': password,
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'role': 'student',
        }
        
        user = User.objects.create_user(
            username=user_data['username'],
            email=user_data['email'],
            password=password,
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            role='student'
        )
        
        # Create Student
        student = super().save(commit=False)
        student.user = user
        student.generated_password = password  # Store plain password for display
        
        if commit:
            student.save()
            self.save_m2m()
        
        # Return ONLY student (not tuple) to match your original return type
        return student