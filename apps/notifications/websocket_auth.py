# apps/notifications/websocket_auth.py
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
import jwt
from django.conf import settings

User = get_user_model()


class WebSocketJWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware for WebSocket JWT authentication.
    
    Supports:
    - Query parameter authentication (?token=...)
    - Cookie authentication
    - Session authentication (for Django sessions)
    """
    
    async def __call__(self, scope, receive, send):
        # Extract token from query string
        query_string = scope.get('query_string', b'').decode()
        token = None
        
        # Try to get token from query parameters
        if query_string:
            params = dict(param.split('=') for param in query_string.split('&') if '=' in param)
            token = params.get('token')
        
        # Try to get token from cookies if not in query params
        if not token:
            headers = dict(scope.get('headers', []))
            cookie_header = headers.get(b'cookie', b'').decode()
            if cookie_header:
                cookies = dict(cookie.split('=', 1) for cookie in cookie_header.split('; ') if '=' in cookie)
                token = cookies.get('access_token') or cookies.get('token')
        
        # Authenticate user
        scope['user'] = await self.get_user_from_token(token) if token else AnonymousUser()
        
        return await super().__call__(scope, receive, send)
    
    @database_sync_to_async
    def get_user_from_token(self, token):
        """Get user from JWT token."""
        try:
            # Try with simplejwt first
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            return User.objects.get(id=user_id)
        except (TokenError, jwt.exceptions.DecodeError, KeyError):
            # Token is invalid or malformed
            return AnonymousUser()
        except User.DoesNotExist:
            # User doesn't exist
            return AnonymousUser()