from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages  # FIXED: Changed from school_messages to messages
from django.http import JsonResponse
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta

from school_messages.models import Message, MessageRecipient, Notification, HolidayNotice
from school_messages.forms import MessageForm, HolidayNoticeForm, QuickMessageForm, BroadcastScheduleForm
from students.models import Student
from teachers.models import Teacher
from accounts.models import User

def is_admin(user):
    return user.is_authenticated and user.is_admin()

def is_teacher(user):
    return user.is_authenticated and user.is_teacher()

def is_student(user):
    return user.is_authenticated and user.is_student()

# ===== Helper Functions =====

def can_view_message(user, message):
    """Check if user has permission to view a message"""
    if user.is_admin() or user == message.sender:
        return True
    
    if user.is_student():
        try:
            student = Student.objects.get(user=user)
            return MessageRecipient.objects.filter(message=message, student=student).exists()
        except Student.DoesNotExist:
            return False
    
    if user.is_teacher():
        try:
            teacher = Teacher.objects.get(user=user)
            return MessageRecipient.objects.filter(message=message, teacher=teacher).exists()
        except Teacher.DoesNotExist:
            return False
    
    return False

def create_notifications_for_message(message):
    """Create notifications for all message recipients"""
    # Get all recipients for this message
    recipients = MessageRecipient.objects.filter(message=message)
    
    notifications_to_create = []
    for recipient in recipients:
        # Determine the user for this recipient
        user = None
        if recipient.student:
            user = recipient.student.user
        elif recipient.teacher:
            user = recipient.teacher.user
        
        if user:
            notifications_to_create.append(
                Notification(
                    user=user,
                    message=message,
                    notification_type='message',
                    title=f"New Message: {message.subject}",
                    content=message.content[:100] + "..." if len(message.content) > 100 else message.content
                )
            )
    
    # Bulk create notifications
    if notifications_to_create:
        Notification.objects.bulk_create(notifications_to_create)

def create_holiday_notifications(holiday):
    """Create notifications for holiday notice"""
    notifications_to_create = []
    
    # Notify students
    if holiday.notify_students:
        students = Student.objects.select_related('user').all()
        for student in students:
            notifications_to_create.append(
                Notification(
                    user=student.user,
                    related_object_id=holiday.id,
                    related_object_type='holiday',
                    notification_type='holiday',
                    title=f"Holiday Notice: {holiday.title}",
                    content=f"School holidays from {holiday.start_date} to {holiday.end_date}"
                )
            )
    
    # Notify teachers
    if holiday.notify_teachers:
        teachers = Teacher.objects.select_related('user').all()
        for teacher in teachers:
            notifications_to_create.append(
                Notification(
                    user=teacher.user,
                    related_object_id=holiday.id,
                    related_object_type='holiday',
                    notification_type='holiday',
                    title=f"Holiday Notice: {holiday.title}",
                    content=f"School holidays from {holiday.start_date} to {holiday.end_date}"
                )
            )
    
    # Bulk create notifications
    if notifications_to_create:
        Notification.objects.bulk_create(notifications_to_create)

def create_recipients_for_all(message):
    """Create message recipients for all users (students and teachers)"""
    recipients_to_create = []
    
    # Add all students
    students = Student.objects.all()
    for student in students:
        recipients_to_create.append(
            MessageRecipient(
                message=message,
                student=student
            )
        )
    
    # Add all teachers
    teachers = Teacher.objects.all()
    for teacher in teachers:
        recipients_to_create.append(
            MessageRecipient(
                message=message,
                teacher=teacher
            )
        )
    
    # Bulk create recipients
    if recipients_to_create:
        MessageRecipient.objects.bulk_create(recipients_to_create)

def create_recipients_for_message(message):
    """Create message recipients for selected students and teachers"""
    recipients_to_create = []
    
    # Add selected students
    for student in message.students.all():
        recipients_to_create.append(
            MessageRecipient(
                message=message,
                student=student
            )
        )
    
    # Add selected teachers
    for teacher in message.teachers.all():
        recipients_to_create.append(
            MessageRecipient(
                message=message,
                teacher=teacher
            )
        )
    
    # Bulk create recipients
    if recipients_to_create:
        MessageRecipient.objects.bulk_create(recipients_to_create)

# ===== Message Views =====

@login_required
def message_list(request):
    """List all messages (admin/teacher view)"""
    if request.user.is_admin():
        all_messages = Message.objects.all()
    elif request.user.is_teacher():
        all_messages = Message.objects.filter(
            Q(sender=request.user) | Q(teachers__user=request.user)
        ).distinct()
    else:
        all_messages = Message.objects.none()
    
    # Get unread count for notifications
    unread_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    # Get recent messages
    recent_messages = all_messages[:10]
    
    return render(request, 'messages/message_list.html', {
        'messages': all_messages,
        'recent_messages': recent_messages,
        'unread_count': unread_count,
    })

@login_required
@user_passes_test(lambda u: u.is_admin() or u.is_teacher())
def message_create(request):
    """Create a new message"""
    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.save()
            form.save_m2m()  # Save many-to-many relationships
            
            # Create message recipients
            if message.send_to_all:
                create_recipients_for_all(message)
            else:
                create_recipients_for_message(message)
            
            # Create notifications for recipients
            create_notifications_for_message(message)
            
            messages.success(request, 'Message sent successfully!')  # CHANGED
            return redirect('message_list')
    else:
        form = MessageForm(user=request.user)
    
    return render(request, 'messages/message_create.html', {
        'form': form,
        'title': 'Send New Message'
    })

@login_required
def message_detail(request, pk):
    """View message details"""
    message = get_object_or_404(Message, pk=pk)
    
    # Check if user has permission to view this message
    if not can_view_message(request.user, message):
        messages.error(request, 'You do not have permission to view this message.')  # CHANGED
        return redirect('inbox')
    
    # Mark as read if recipient
    if request.user.is_student():
        try:
            student = Student.objects.get(user=request.user)
            recipient = MessageRecipient.objects.get(message=message, student=student)
            recipient.mark_as_read()
        except (Student.DoesNotExist, MessageRecipient.DoesNotExist):
            pass
    elif request.user.is_teacher():
        try:
            teacher = Teacher.objects.get(user=request.user)
            recipient = MessageRecipient.objects.get(message=message, teacher=teacher)
            recipient.mark_as_read()
        except (Teacher.DoesNotExist, MessageRecipient.DoesNotExist):
            pass
    
    # Get recipient statistics
    total_recipients = MessageRecipient.objects.filter(message=message).count()
    read_count = MessageRecipient.objects.filter(message=message, is_read=True).count()
    acknowledged_count = MessageRecipient.objects.filter(message=message, acknowledged=True).count()
    
    return render(request, 'messages/message_detail.html', {
        'message': message,
        'total_recipients': total_recipients,
        'read_count': read_count,
        'acknowledged_count': acknowledged_count,
        'read_percentage': (read_count / total_recipients * 100) if total_recipients > 0 else 0,
    })

@login_required
def inbox(request):
    """User's inbox with received messages"""
    user = request.user
    
    if user.is_student():
        try:
            student = Student.objects.get(user=user)
            recipients = MessageRecipient.objects.filter(student=student).select_related('message')
            messages_list = [recipient.message for recipient in recipients]  # Renamed to avoid conflict
        except Student.DoesNotExist:
            messages_list = []
    elif user.is_teacher():
        try:
            teacher = Teacher.objects.get(user=user)
            recipients = MessageRecipient.objects.filter(teacher=teacher).select_related('message')
            messages_list = [recipient.message for recipient in recipients]  # Renamed to avoid conflict
        except Teacher.DoesNotExist:
            messages_list = []
    else:
        # Admin sees all messages they sent
        messages_list = Message.objects.filter(sender=user)  # Renamed to avoid conflict
    
    # Get unread messages
    unread_messages = []
    read_messages = []
    
    for msg in messages_list:
        if user.is_student():
            recipient = MessageRecipient.objects.filter(message=msg, student__user=user).first()
        elif user.is_teacher():
            recipient = MessageRecipient.objects.filter(message=msg, teacher__user=user).first()
        else:
            recipient = None
        
        if recipient and not recipient.is_read:
            unread_messages.append({
                'message': msg,
                'recipient': recipient,
                'is_read': False
            })
        else:
            read_messages.append({
                'message': msg,
                'recipient': recipient,
                'is_read': True
            })
    
    return render(request, 'messages/inbox.html', {
        'unread_messages': unread_messages,
        'read_messages': read_messages,
        'total_messages': len(messages_list),
        'unread_count': len(unread_messages),
    })

@login_required
def outbox(request):
    """Messages sent by the user"""
    if not (request.user.is_admin() or request.user.is_teacher()):
        messages.error(request, 'Access denied.')  # CHANGED
        return redirect('dashboard')
    
    sent_messages = Message.objects.filter(sender=request.user)
    
    # Get delivery statistics for each message
    messages_with_stats = []
    for msg in sent_messages:
        recipients = MessageRecipient.objects.filter(message=msg)
        total = recipients.count()
        read = recipients.filter(is_read=True).count()
        acknowledged = recipients.filter(acknowledged=True).count()
        
        messages_with_stats.append({
            'message': msg,
            'total_recipients': total,
            'read_count': read,
            'acknowledged_count': acknowledged,
            'read_percentage': (read / total * 100) if total > 0 else 0,
        })
    
    return render(request, 'messages/outbox.html', {
        'messages': messages_with_stats,
    })

# ===== Holiday Notices =====

@login_required
@user_passes_test(is_admin)
def holiday_notice_list(request):
    """List all holiday notices"""
    holidays = HolidayNotice.objects.all()
    current_holidays = [h for h in holidays if h.is_current()]
    upcoming_holidays = [h for h in holidays if h.start_date > timezone.now().date()]
    past_holidays = [h for h in holidays if h.end_date < timezone.now().date()]
    
    return render(request, 'messages/holiday_list.html', {
        'current_holidays': current_holidays,
        'upcoming_holidays': upcoming_holidays,
        'past_holidays': past_holidays,
    })

@login_required
@user_passes_test(is_admin)
def holiday_notice_create(request):
    """Create a holiday notice"""
    if request.method == 'POST':
        form = HolidayNoticeForm(request.POST)
        if form.is_valid():
            holiday = form.save(commit=False)
            holiday.created_by = request.user
            
            # Check for date validity
            if holiday.start_date > holiday.end_date:
                form.add_error('end_date', 'End date must be after start date.')
            elif holiday.end_date > holiday.school_reopens:
                form.add_error('school_reopens', 'School reopens date must be after holiday end date.')
            else:
                holiday.save()
                
                # Send notifications if requested
                if holiday.notify_students or holiday.notify_parents or holiday.notify_teachers:
                    create_holiday_notifications(holiday)
                
                messages.success(request, 'Holiday notice created and notifications sent!')  # CHANGED
                return redirect('holiday_notice_list')
    else:
        form = HolidayNoticeForm()
    
    return render(request, 'messages/holiday_form.html', {
        'form': form,
        'title': 'Create Holiday Notice'
    })

@login_required
def holiday_notice_detail(request, pk):
    """View holiday notice details"""
    holiday = get_object_or_404(HolidayNotice, pk=pk)
    
    # Calculate days remaining or elapsed
    today = timezone.now().date()
    if today < holiday.start_date:
        status = 'upcoming'
        days_info = f"Starts in {(holiday.start_date - today).days} days"
    elif today > holiday.end_date:
        status = 'past'
        days_info = f"Ended {(today - holiday.end_date).days} days ago"
    else:
        status = 'current'
        days_info = f"Day {(today - holiday.start_date).days + 1} of {holiday.duration_days}"
    
    return render(request, 'messages/holiday_detail.html', {
        'holiday': holiday,
        'status': status,
        'days_info': days_info,
    })

# ===== Notifications =====

@login_required
def notification_list(request):
    """User's notifications"""
    user_notifications = Notification.objects.filter(user=request.user)
    unread_notifications = user_notifications.filter(is_read=False)
    read_notifications = user_notifications.filter(is_read=True)[:20]  # Limit read notifications
    
    return render(request, 'messages/notification_list.html', {
        'unread_notifications': unread_notifications,
        'read_notifications': read_notifications,
        'total_unread': unread_notifications.count(),
    })

@login_required
def mark_notification_read(request, pk):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notification_list')

@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notification_list')

@login_required
def get_notification_count(request):
    """Get unread notification count (AJAX)"""
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return JsonResponse({'count': count})
    return JsonResponse({'count': 0})

# ===== Quick Actions =====

@login_required
@user_passes_test(lambda u: u.is_admin() or u.is_teacher())
def quick_message(request):
    """Quick message sending interface"""
    if request.method == 'POST':
        form = QuickMessageForm(request.POST)
        if form.is_valid():
            subject_type = form.cleaned_data['subject_type']
            custom_subject = form.cleaned_data['custom_subject']
            content = form.cleaned_data['content']
            send_to = form.cleaned_data['send_to']
            
            # Create subject based on type
            subject_map = {
                'holiday': 'Holiday Notice',
                'fee_reminder': 'Fee Payment Reminder',
                'exam_schedule': 'Exam Schedule Update',
                'event': 'School Event Announcement',
                'urgent': 'Urgent Notice',
            }
            subject = custom_subject if custom_subject else subject_map.get(subject_type, 'Message')
            
            # Create message
            message = Message.objects.create(
                sender=request.user,
                subject=subject,
                content=content,
                message_type='announcement',
                priority='high' if subject_type == 'urgent' else 'normal'
            )
            
            # Add recipients based on selection
            if send_to == 'all_students':
                message.send_to_all = False
                message.students.set(Student.objects.all())
            elif send_to == 'all_teachers':
                message.send_to_all = False
                message.teachers.set(Teacher.objects.all())
            elif send_to == 'all_users':
                message.send_to_all = True
            # For 'specific', you would need additional form fields
            
            message.save()
            
            # Create recipients and notifications
            if message.send_to_all:
                create_recipients_for_all(message)
            else:
                create_recipients_for_message(message)
            
            create_notifications_for_message(message)
            
            messages.success(request, 'Quick message sent successfully!')  # CHANGED
            return redirect('message_list')
    else:
        form = QuickMessageForm()
    
    return render(request, 'messages/quick_message.html', {'form': form})