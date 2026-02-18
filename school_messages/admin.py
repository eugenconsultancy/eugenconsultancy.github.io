from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Message, MessageRecipient, Notification, HolidayNotice, BroadcastSchedule

@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = ('subject', 'sender', 'message_type', 'priority', 'is_published', 'created_at')
    list_filter = ('message_type', 'priority', 'is_published', 'created_at')
    search_fields = ('subject', 'content', 'sender__username')
    readonly_fields = ('created_at', 'published_at')
    fieldsets = (
        ('Message Information', {
            'fields': ('sender', 'subject', 'content', 'message_type', 'priority')
        }),
        ('Recipients', {
            'fields': ('send_to_all', 'students', 'teachers')
        }),
        ('Status & Delivery', {
            'fields': ('is_published', 'requires_acknowledgement', 'attachments', 'tags')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'scheduled_for', 'published_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(MessageRecipient)
class MessageRecipientAdmin(ModelAdmin):
    list_display = ('message', 'student', 'teacher', 'is_read', 'acknowledged', 'email_sent', 'sms_sent')
    list_filter = ('is_read', 'acknowledged', 'email_sent', 'sms_sent')
    search_fields = ('message__subject', 'student__user__username', 'teacher__user__username')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ('user', 'title', 'notification_type', 'is_read', 'is_important', 'created_at')
    list_filter = ('notification_type', 'is_read', 'is_important', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('created_at',)

@admin.register(HolidayNotice)
class HolidayNoticeAdmin(ModelAdmin):
    list_display = ('title', 'start_date', 'end_date', 'school_reopens', 'is_active')
    list_filter = ('is_active', 'start_date', 'end_date')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Holiday Information', {
            'fields': ('title', 'description', 'start_date', 'end_date', 'school_reopens')
        }),
        ('Notification Settings', {
            'fields': ('notify_students', 'notify_parents', 'notify_teachers')
        }),
        ('Additional Information', {
            'fields': ('important_notes', 'contact_person', 'contact_phone')
        }),
        ('Administration', {
            'fields': ('created_by', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(BroadcastSchedule)
class BroadcastScheduleAdmin(ModelAdmin):
    list_display = ('message', 'frequency', 'scheduled_time', 'is_active', 'last_sent')
    list_filter = ('frequency', 'is_active')
    search_fields = ('message__subject',)
    readonly_fields = ('last_sent', 'next_send', 'created_at', 'updated_at')