from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    )
    
    TEACHER_ROLE_CHOICES = (
        ('teacher', 'Regular Teacher'),
        ('deputy_principal', 'Deputy Principal'),
        ('hod', 'Head of Department'),
        ('sports_master', 'Sports Master'),
        ('academic_head', 'Academic Head'),
        ('discipline_master', 'Discipline Master'),
        ('activity_coordinator', 'Activity Coordinator'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    teacher_role = models.CharField(max_length=20, choices=TEACHER_ROLE_CHOICES, default='teacher', blank=True)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_teacher(self):
        return self.role == 'teacher'
    
    def is_student(self):
        return self.role == 'student'
    
    def get_teacher_role_display_name(self):
        if self.is_teacher():
            for value, label in self.TEACHER_ROLE_CHOICES:
                if value == self.teacher_role:
                    return label
        return "Not a Teacher"
    
    # ADDED: Check if user has student profile
    def has_student_profile(self):
        """Check if user has a linked student profile"""
        return hasattr(self, 'student_profile')
    
    # ADDED: Check if user has teacher profile
    def has_teacher_profile(self):
        """Check if user has a linked teacher profile"""
        return hasattr(self, 'teacher_profile')
    
    # ADDED: Get student profile if exists
    def get_student_profile(self):
        """Get the student profile linked to this user"""
        if self.has_student_profile():
            return self.student_profile
        return None
    
    # ADDED: Get teacher profile if exists
    def get_teacher_profile(self):
        """Get the teacher profile linked to this user"""
        if self.has_teacher_profile():
            return self.teacher_profile
        return None