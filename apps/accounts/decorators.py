from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

def admin_required(view_func):
    """
    Decorator for views that checks that the user is a superuser or staff,
    raising a PermissionDenied exception if necessary.
    """
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view


def writer_required(view_func):
    """
    Decorator for views that checks that the user is marked as a writer.
    """
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.user_type == 'writer':
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view


def client_required(view_func):
    """
    Decorator for views that checks that the user is a client.
    Note: Your model uses 'client' not 'customer' as user_type.
    """
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.user_type == 'client':
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view


# Add customer_required as an alias for backward compatibility
# (since your reviews views expect customer_required)
def customer_required(view_func):
    """
    Alias for client_required for backward compatibility.
    """
    return client_required(view_func)


# Optional: Additional decorators based on your user model
def moderator_required(view_func):
    """
    Decorator for views that checks that the user is a moderator.
    """
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.user_type == 'moderator':
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view


def staff_or_admin_required(view_func):
    """
    Decorator for views that checks that the user is staff or admin.
    """
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            if (request.user.is_staff or 
                request.user.is_superuser or 
                request.user.user_type in ['admin', 'moderator']):
                return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view