# apps/messaging/routing.py
from django.urls import re_path
from apps.messaging import consumers

websocket_urlpatterns = [
    re_path(r'ws/messaging/conversations/(?P<conversation_id>[^/]+)/$', 
            consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/notifications/$', 
            consumers.NotificationConsumer.as_asgi()),
]