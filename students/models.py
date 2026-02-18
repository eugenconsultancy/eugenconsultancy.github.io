from django.db import models
from accounts.models import User

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    admission_number = models.CharField(max_length=20, unique=True)
    grade = models.CharField(max_length=10)
    section = models.CharField(max_length=10)
    date_of_birth = models.DateField()
    address = models.TextField()
    phone = models.CharField(max_length=15, blank=True)
    parent_name = models.CharField(max_length=100)
    parent_phone = models.CharField(max_length=15)
    
    clubs = models.TextField(blank=True, help_text="List of clubs registered (comma-separated)")
    societies = models.TextField(blank=True, help_text="List of societies joined (comma-separated)")
    subjects = models.TextField(blank=True, help_text="Subjects enrolled (comma-separated)")
    
    # Add field to store initial password for teacher viewing
    initial_password = models.CharField(max_length=128, blank=True, null=True, editable=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.admission_number}"
    
    def save(self, *args, **kwargs):
        # Store the initial password when first created
        if not self.pk and not self.initial_password and self.user:
            # For demo: create a simple password based on student info
            # In production, this would come from the password generation function
            pass_first = self.user.first_name[:3].lower() if self.user.first_name else 'stu'
            pass_last = self.admission_number[-2:]
            self.initial_password = f"{pass_first}{pass_last}1@"
        
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['grade', 'section', 'admission_number']