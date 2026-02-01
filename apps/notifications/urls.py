# apps/notifications/urls.py
from django.urls import path
from apps.notifications import views

app_name = 'notifications'

urlpatterns = [
    # User endpoints
    path('', views.NotificationListView.as_view(), name='notification_list'),
    path('unread/', views.UnreadNotificationListView.as_view(), name='unread_notifications'),
    path('mark-all-read/', views.MarkAllAsReadView.as_view(), name='mark_all_read'),
    path('<uuid:notification_id>/read/', views.MarkAsReadView.as_view(), name='mark_as_read'),
    path('preferences/', views.NotificationPreferencesView.as_view(), name='preferences'),
    path('preferences/update/', views.UpdatePreferencesView.as_view(), name='update_preferences'),
    path('digest/unsubscribe/', views.UnsubscribeDigestView.as_view(), name='unsubscribe_digest'),
    
    # Admin endpoints
    path('admin/test/', views.TestNotificationView.as_view(), name='test_notification'),
    path('admin/analytics/', views.NotificationAnalyticsView.as_view(), name='notification_analytics'),
    path('admin/engagement/', views.UserEngagementView.as_view(), name='user_engagement'),
    path('admin/logs/', views.NotificationLogListView.as_view(), name='notification_logs'),
]