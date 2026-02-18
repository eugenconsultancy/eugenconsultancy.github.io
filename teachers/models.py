from django.db import models
from accounts.models import User
from students.models import Student

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100)
    subjects = models.TextField(help_text="Subjects taught (comma-separated)")
    classes = models.TextField(help_text="Classes/Grades taught (comma-separated)")
    
    # Link to specific subjects from marks app - use string reference
    assigned_subjects = models.ManyToManyField('marks.Subject', blank=True, related_name='teachers')
    
    # Additional information
    qualification = models.CharField(max_length=200)
    experience = models.CharField(max_length=100)
    specialization = models.CharField(max_length=200, blank=True)
    
    # Extra roles and responsibilities
    extra_roles = models.TextField(blank=True, help_text="Additional roles and responsibilities")
    extracurricular_activities = models.TextField(blank=True, help_text="Extracurricular activities supervised")
    
    # Contact information
    phone = models.CharField(max_length=15)
    office_room = models.CharField(max_length=20, blank=True)
    
    # ADDED: Store initial password for admin viewing
    initial_password = models.CharField(max_length=128, blank=True, null=True, editable=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.employee_id}"
    
    def get_subjects_list(self):
        return [s.strip() for s in self.subjects.split(',')]
    
    def get_classes_list(self):
        return [c.strip() for c in self.classes.split(',')]
    
    def get_assigned_students(self):
        # Get students based on teacher's classes
        assigned_students = []
        for class_name in self.get_classes_list():
            students = Student.objects.filter(grade=class_name)
            assigned_students.extend(students)
        return assigned_students
    
    def save(self, *args, **kwargs):
        """
        Override save method to store initial password when teacher is first created.
        This password is for admin reference and teacher password viewing.
        """
        is_new = not self.pk
        
        # Call parent save first to ensure we have a PK
        super().save(*args, **kwargs)
        
        # Store initial password for new teachers
        if is_new and not self.initial_password and self.user:
            # Generate a simple password pattern for reference
            # Format: teach{first_3_of_emp_id}{random_2_digits}@
            emp_prefix = self.employee_id[:3].lower() if len(self.employee_id) >= 3 else 'tea'
            import random
            random_digits = str(random.randint(10, 99))
            self.initial_password = f"teach{emp_prefix}{random_digits}@"
            
            # Save again with the initial password
            super().save(update_fields=['initial_password'])
    
    class Meta:
        ordering = ['department', 'employee_id']