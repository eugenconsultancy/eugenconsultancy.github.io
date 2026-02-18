from django import forms
from .models import Message, HolidayNotice, BroadcastSchedule
from students.models import Student
from teachers.models import Teacher
from django.utils import timezone

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = [
            'subject', 'content', 'message_type', 'priority',
            'send_to_all', 'students', 'teachers',
            'requires_acknowledgement', 'attachments', 'tags'
        ]
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter message subject'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Enter message content'}),
            'students': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'teachers': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'tags': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., holiday, fees, exam'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # If user is teacher, only show their students
        if user and user.is_teacher():
            try:
                teacher = Teacher.objects.get(user=user)
                student_list = []
                for class_name in teacher.get_classes_list():
                    students = Student.objects.filter(grade=class_name)
                    student_list.extend(students)
                self.fields['students'].queryset = Student.objects.filter(id__in=[s.id for s in student_list])
            except Teacher.DoesNotExist:
                self.fields['students'].queryset = Student.objects.none()

class HolidayNoticeForm(forms.ModelForm):
    class Meta:
        model = HolidayNotice
        fields = [
            'title', 'description', 'start_date', 'end_date',
            'school_reopens', 'important_notes',
            'contact_person', 'contact_phone',
            'notify_students', 'notify_parents', 'notify_teachers'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'school_reopens': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'important_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class BroadcastScheduleForm(forms.ModelForm):
    class Meta:
        model = BroadcastSchedule
        fields = ['frequency', 'scheduled_time', 'start_date', 'end_date', 'is_active']
        widgets = {
            'scheduled_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

class QuickMessageForm(forms.Form):
    SUBJECT_CHOICES = (
        ('holiday', 'Holiday Notice'),
        ('fee_reminder', 'Fee Reminder'),
        ('exam_schedule', 'Exam Schedule'),
        ('event', 'School Event'),
        ('urgent', 'Urgent Notice'),
    )
    
    subject_type = forms.ChoiceField(choices=SUBJECT_CHOICES)
    custom_subject = forms.CharField(required=False, max_length=200)
    content = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}))
    send_to = forms.ChoiceField(choices=[
        ('all_students', 'All Students'),
        ('all_teachers', 'All Teachers'),
        ('all_users', 'All Users'),
        ('specific', 'Specific Recipients')
    ])
    
    def clean(self):
        cleaned_data = super().clean()
        subject_type = cleaned_data.get('subject_type')
        custom_subject = cleaned_data.get('custom_subject')
        
        if subject_type == 'custom' and not custom_subject:
            raise forms.ValidationError("Custom subject is required when 'Custom' is selected.")
        
        return cleaned_data