# apps/messaging/urls.py
from django.urls import path
from apps.messaging import views

app_name = 'messaging'

urlpatterns = [
    # User endpoints
    path('conversations/', views.ConversationListView.as_view(), name='conversation_list'),
    path('conversations/<uuid:conversation_id>/', views.ConversationDetailView.as_view(), name='conversation_detail'),
    path('conversations/<uuid:conversation_id>/messages/', views.MessageListView.as_view(), name='message_list'),
    path('conversations/<uuid:conversation_id>/send/', views.SendMessageView.as_view(), name='send_message'),
    path('conversations/<uuid:conversation_id>/stats/', views.ConversationStatsView.as_view(), name='conversation_stats'),
    path('conversations/<uuid:conversation_id>/close/', views.CloseConversationView.as_view(), name='close_conversation'),
    
    # Message endpoints
    path('messages/<uuid:message_id>/read/', views.MarkMessageReadView.as_view(), name='mark_message_read'),
    
    # Attachment endpoints
    path('attachments/<uuid:attachment_id>/download/', views.DownloadAttachmentView.as_view(), name='download_attachment'),
    
    # Admin endpoints
    path('admin/conversations/', views.AdminConversationListView.as_view(), name='admin_conversation_list'),
]