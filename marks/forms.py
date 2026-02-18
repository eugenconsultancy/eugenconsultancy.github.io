from django import forms
from .models import Mark, Subject, StudentReport
from students.models import Student
from teachers.models import Teacher

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'category', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class MarkForm(forms.ModelForm):
    class Meta:
        model = Mark
        fields = [
            'student', 'subject', 'cat1_score', 'cat2_score', 
            'main_exam_score', 'term', 'academic_year', 'comments'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'cat1_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cat2_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'main_exam_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'term': forms.Select(choices=[
                ('Term 1', 'Term 1'),
                ('Term 2', 'Term 2'),
                ('Term 3', 'Term 3'),
                ('Term 4', 'Term 4'),
            ], attrs={'class': 'form-control'}),
            'academic_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2024'}),
            'comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        
        if teacher:
            # Filter students based on teacher's classes
            self.fields['student'].queryset = Student.objects.filter(
                grade__in=teacher.get_classes_list()
            )

class MarkUpdateForm(forms.ModelForm):
    class Meta:
        model = Mark
        fields = ['cat1_score', 'cat2_score', 'main_exam_score', 'comments']
        widgets = {
            'cat1_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cat2_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'main_exam_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class StudentReportForm(forms.ModelForm):
    class Meta:
        model = StudentReport
        fields = [
            'student', 'term', 'academic_year', 'average_score',
            'overall_grade', 'class_position', 'total_students',
            'teacher_comment', 'principal_comment',
            'days_present', 'total_days'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'term': forms.Select(choices=[
                ('Term 1', 'Term 1'),
                ('Term 2', 'Term 2'),
                ('Term 3', 'Term 3'),
                ('Term 4', 'Term 4'),
            ], attrs={'class': 'form-control'}),
            'academic_year': forms.TextInput(attrs={'class': 'form-control'}),
            'average_score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'overall_grade': forms.Select(choices=Mark.GRADE_CHOICES, attrs={'class': 'form-control'}),
            'class_position': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_students': forms.NumberInput(attrs={'class': 'form-control'}),
            'teacher_comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'principal_comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'days_present': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_days': forms.NumberInput(attrs={'class': 'form-control'}),
        }