from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta  # ADD THIS IMPORT
from students.models import Student
from teachers.models import Teacher

class Message(models.Model):
    MESSAGE_TYPES = (
        ('announcement', 'Announcement'),
        ('holiday', 'Holiday Notice'),
        ('academic', 'Academic Update'),
        ('fee', 'Fee Reminder'),
        ('event', 'Event Information'),
        ('general', 'General Message'),
        ('urgent', 'Urgent Notice'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    subject = models.CharField(max_length=200)
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='general')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Recipient options
    send_to_all = models.BooleanField(default=False)
    students = models.ManyToManyField(Student, blank=True, related_name='received_messages')
    teachers = models.ManyToManyField(Teacher, blank=True, related_name='received_messages')
    
    # Status
    is_published = models.BooleanField(default=True)
    requires_acknowledgement = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    attachments = models.FileField(upload_to='message_attachments/', null=True, blank=True)
    tags = models.CharField(max_length=200, blank=True, help_text="Comma-separated tags")
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subject} - {self.get_message_type_display()}"
    
    def save(self, *args, **kwargs):
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
    
    @property
    def total_recipients(self):
        if self.send_to_all:
            return "All users"
        else:
            student_count = self.students.count()
            teacher_count = self.teachers.count()
            return student_count + teacher_count

class MessageRecipient(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='recipients')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, null=True, blank=True)
    
    # Read status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Acknowledgment
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_note = models.TextField(blank=True)
    
    # Delivery
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    sms_sent = models.BooleanField(default=False)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['message', 'student'], ['message', 'teacher']]
    
    def __str__(self):
        recipient = self.student if self.student else self.teacher
        return f"{recipient} - {self.message.subject}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def acknowledge(self, note=''):
        if not self.acknowledged:
            self.acknowledged = True
            self.acknowledged_at = timezone.now()
            self.acknowledgement_note = note
            self.save()


class HolidayNotice(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    
    # Recipients
    notify_students = models.BooleanField(default=True)
    notify_parents = models.BooleanField(default=True)
    notify_teachers = models.BooleanField(default=True)
    
    # Additional info
    school_reopens = models.DateField()
    important_notes = models.TextField(blank=True)
    contact_person = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = "Holiday Notice"
        verbose_name_plural = "Holiday Notices"
    
    def __str__(self):
        return f"{self.title} ({self.start_date} to {self.end_date})"
    
    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1
    
    def is_current(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date
    
    @property
    def days_until_start(self):
        today = timezone.now().date()
        if today < self.start_date:
            return (self.start_date - today).days
        return 0
    
    @property
    def days_until_reopen(self):
        today = timezone.now().date()
        if today < self.school_reopens:
            return (self.school_reopens - today).days
        return 0


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('message', 'New Message'),
        ('fee', 'Fee Reminder'),
        ('mark', 'Marks Posted'),
        ('holiday', 'Holiday Notice'),
        ('event', 'Upcoming Event'),
        ('system', 'System Update'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    
    # Relationship to the actual object (optional)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    holiday_notice = models.ForeignKey('HolidayNotice', on_delete=models.SET_NULL, null=True, blank=True)
    
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    
    # Content fields - ADD default value
    content = models.TextField(default='No content available')  # ADD default
    short_content = models.CharField(max_length=100, blank=True)
    
    # Link for navigation
    link = models.CharField(max_length=200, blank=True)
    
    # Related object tracking (for generic relationships)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object_type = models.CharField(max_length=50, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def get_absolute_url(self):
        if self.link:
            return self.link
        elif self.message:
            return f"/messages/{self.message.id}/"
        elif self.holiday_notice:
            return f"/messages/holidays/{self.holiday_notice.id}/"
        return "#"


class BroadcastSchedule(models.Model):
    FREQUENCY_CHOICES = (
        ('once', 'Once'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    )
    
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name='schedule')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='once')
    scheduled_time = models.TimeField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Days of week (for weekly scheduling)
    monday = models.BooleanField(default=False)
    tuesday = models.BooleanField(default=False)
    wednesday = models.BooleanField(default=False)
    thursday = models.BooleanField(default=False)
    friday = models.BooleanField(default=False)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)
    
    last_sent = models.DateTimeField(null=True, blank=True)
    next_send = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['next_send', 'start_date']
        verbose_name = "Broadcast Schedule"
        verbose_name_plural = "Broadcast Schedules"
    
    def __str__(self):
        return f"{self.message.subject} - {self.frequency}"
    
    def calculate_next_send(self):
        """Calculate when to send next based on frequency"""
        now = timezone.now()
        
        if self.frequency == 'once':
            # Send once at start_date + scheduled_time
            next_date = datetime.combine(self.start_date, self.scheduled_time)
            self.next_send = timezone.make_aware(next_date)
        
        elif self.frequency == 'daily':
            # Send daily at scheduled_time
            next_date = now.date()
            next_time = datetime.combine(next_date, self.scheduled_time)
            next_datetime = timezone.make_aware(next_time)
            
            if next_datetime <= now:
                next_date += timedelta(days=1)
                next_time = datetime.combine(next_date, self.scheduled_time)
                next_datetime = timezone.make_aware(next_time)
            
            self.next_send = next_datetime
        
        elif self.frequency == 'weekly':
            # Send weekly on selected days
            # This is more complex - you'd need to find the next selected day
            pass
        
        elif self.frequency == 'monthly':
            # Send monthly on the same day of month
            pass
        
        self.save()
    
    def should_send_now(self):
        """Check if it's time to send the message"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        
        # Check if within date range
        if self.end_date and now.date() > self.end_date:
            return False
        
        # Check if it's time to send
        if self.next_send and now >= self.next_send:
            return True
        
        return False