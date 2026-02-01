# config/routing.py (updated with authentication)
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from apps.notifications.websocket_auth import WebSocketJWTAuthMiddleware
import apps.messaging.routing
import apps.notifications.routing

# Combine WebSocket URL patterns from all apps
websocket_urlpatterns = (
    apps.messaging.routing.websocket_urlpatterns +
    apps.notifications.routing.websocket_urlpatterns
)

application = ProtocolTypeRouter({
    'websocket': WebSocketJWTAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})