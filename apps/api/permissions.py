"""
API permissions for secure access control.
"""
from rest_framework import permissions
from django.contrib.auth import get_user_model
from apps.accounts.models import User
# Fixed import - changed from APIKey to APIToken
from apps.api.models import APIToken
from django.utils import timezone

class IsAdminUser(permissions.BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Allows access only to object owners or admin users.
    """
    def has_object_permission(self, request, view, obj):
        # Admin users can do anything
        if request.user and request.user.is_staff:
            return True
        
        # Check if object has an 'owner' attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'client'):
            return obj.client == request.user
        elif hasattr(obj, 'writer'):
            return obj.writer == request.user
        elif hasattr(obj, 'opened_by'):
            return obj.opened_by == request.user
        elif hasattr(obj, 'submitted_by'):
            return obj.submitted_by == request.user
        
        # Default to safe methods for non-owner
        return request.method in permissions.SAFE_METHODS


class IsOrderPartyOrAdmin(permissions.BasePermission):
    """
    Allows access only to order parties (client/writer) or admin users.
    """
    def has_object_permission(self, request, view, obj):
        # Admin users can do anything
        if request.user and request.user.is_staff:
            return True
        
        # Check if user is client or writer for this order
        if hasattr(obj, 'order'):
            order = obj.order
            return request.user in [order.client, order.writer]
        elif hasattr(obj, 'client') and hasattr(obj, 'writer'):
            return request.user in [obj.client, obj.writer]
        
        return False


class IsVerifiedWriter(permissions.BasePermission):
    """
    Allows access only to verified writers.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin users can do anything
        if request.user.is_staff:
            return True
        
        # Check if user is a verified writer
        return (
            request.user.role == User.Role.WRITER and
            request.user.writer_profile.is_verified
        )


class IsClientUser(permissions.BasePermission):
    """
    Allows access only to client users.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin users can do anything
        if request.user.is_staff:
            return True
        
        return request.user.role == User.Role.CLIENT


class IsWriterUser(permissions.BasePermission):
    """
    Allows access only to writer users.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin users can do anything
        if request.user.is_staff:
            return True
        
        return request.user.role == User.Role.WRITER


class ReadOnlyOrAdmin(permissions.BasePermission):
    """
    Allows read-only access to all users, write access only to admin users.
    """
    def has_permission(self, request, view):
        # Allow read-only for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Write methods require admin
        return request.user and request.user.is_staff


class HasAPIAccess(permissions.BasePermission):
    """
    Custom permission for API key access.
    Used for external integrations.
    """
    def has_permission(self, request, view):
        # Check for API key in headers
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return False
        
        # Validate API key - changed from APIKey to APIToken
        try:
            api_token_obj = APIToken.objects.get(token=api_key, is_active=True)
            
            # Check if token is expired
            if api_token_obj.expires_at and api_token_obj.expires_at < timezone.now():
                return False
            
            # Store API key info in request for later use
            request.api_token = api_token_obj
            return True
            
        except APIToken.DoesNotExist:
            return False


class RateLimitedPermission(permissions.BasePermission):
    """
    Rate limiting permission based on user or IP.
    """
    def has_permission(self, request, view):
        # Get rate limit configuration from view
        rate_limit = getattr(view, 'rate_limit', None)
        if not rate_limit:
            return True
        
        # Implement rate limiting logic here
        # This would typically use Django Ratelimit or similar
        return True


class DisputeAccessPermission(permissions.BasePermission):
    """
    Special permission for dispute-related endpoints.
    Only allows access to dispute parties or admin.
    """
    def has_object_permission(self, request, view, obj):
        # Admin users can do anything
        if request.user and request.user.is_staff:
            return True
        
        # Check if object is a dispute
        if hasattr(obj, 'dispute'):
            dispute = obj.dispute
            return request.user in [dispute.opened_by, dispute.against_user]
        elif hasattr(obj, 'opened_by') and hasattr(obj, 'against_user'):
            return request.user in [obj.opened_by, obj.against_user]
        
        return False


class PlagiarismReportAccessPermission(permissions.BasePermission):
    """
    Special permission for plagiarism report access.
    Only admin users can access plagiarism reports.
    """
    def has_permission(self, request, view):
        # Admin users can do anything
        if request.user and request.user.is_staff:
            return True
        
        # For specific report access via access key
        if view.action == 'retrieve_by_access_key':
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        # Admin users can do anything
        if request.user and request.user.is_staff:
            return True
        
        # Check if user is admin
        return request.user and request.user.is_staff