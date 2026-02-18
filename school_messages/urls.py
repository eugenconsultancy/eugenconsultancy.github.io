from django.urls import path
from . import views

urlpatterns = [
    # Message management
    path('', views.message_list, name='message_list'),
    path('create/', views.message_create, name='message_create'),
    path('<int:pk>/', views.message_detail, name='message_detail'),
    
    # User inbox/outbox
    path('inbox/', views.inbox, name='inbox'),
    path('outbox/', views.outbox, name='outbox'),
    
    # Holiday notices
    path('holidays/', views.holiday_notice_list, name='holiday_notice_list'),
    path('holidays/create/', views.holiday_notice_create, name='holiday_notice_create'),
    path('holidays/<int:pk>/', views.holiday_notice_detail, name='holiday_notice_detail'),
    
    # Notifications
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/count/', views.get_notification_count, name='get_notification_count'),
    
    # Quick actions
    path('quick/', views.quick_message, name='quick_message'),
]