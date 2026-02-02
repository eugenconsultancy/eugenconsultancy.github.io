from django import template
from django.utils import timezone

register = template.Library()

# --- Security & Device Filters ---

@register.filter(name='device_icon')
def device_icon(value):
    """Maps device/OS strings to FontAwesome icon names for security logs."""
    if not value:
        return "laptop"
    v = str(value).lower()
    if any(x in v for x in ['iphone', 'android', 'mobile', 'phone']):
        return "mobile-alt"
    if any(x in v for x in ['ipad', 'tablet']):
        return "tablet-alt"
    if any(x in v for x in ['windows', 'mac', 'linux', 'desktop']):
        return "desktop"
    return "laptop"

# --- Status & Color Filters ---

@register.filter
def state_color(state):
    """Return Bootstrap color class for writer verification state."""
    color_map = {
        'registered': 'secondary',
        'profile_completed': 'info',
        'documents_submitted': 'primary',
        'under_admin_review': 'warning',
        'approved': 'success',
        'rejected': 'danger',
        'revision_required': 'warning',
    }
    return color_map.get(state, 'secondary')

@register.filter
def status_color(status):
    """Return Bootstrap color class for document status."""
    color_map = {
        'pending': 'warning',
        'verified': 'success',
        'rejected': 'danger',
        'expired': 'secondary',
    }
    return color_map.get(status, 'secondary')

@register.filter
def request_status_color(status):
    """Return Bootstrap color class for data request status."""
    color_map = {
        'received': 'secondary',
        'verifying': 'warning',
        'processing': 'info',
        'completed': 'success',
        'rejected': 'danger',
        'cancelled': 'secondary',
    }
    return color_map.get(status, 'secondary')

# --- Document & Icon Filters ---

@register.filter
def document_icon(document_type):
    """Return FontAwesome icon class for document types."""
    icon_map = {
        'id_proof': 'fa-id-card',
        'degree_certificate': 'fa-certificate',
        'transcript': 'fa-scroll',
        'cv': 'fa-file-alt',
        'portfolio': 'fa-folder-open',
        'other': 'fa-file',
    }
    return icon_map.get(document_type, 'fa-file')

@register.filter
def document_icon_class(document_type):
    """Return custom CSS category class for document icons."""
    class_map = {
        'id_proof': 'id',
        'degree_certificate': 'certificate',
        'transcript': 'word',
        'cv': 'pdf',
        'portfolio': 'pdf',
        'other': 'word',
    }
    return class_map.get(document_type, 'word')

# --- Math & String Utilities ---

@register.filter
def split(value, delimiter=','):
    """Split string by delimiter."""
    return value.split(delimiter) if value else []

@register.filter
def strip(value):
    """Strip whitespace from string."""
    return str(value).strip() if value else ""

@register.filter
def subtract(value, arg):
    """Subtract arg from value."""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def filesizeformat(value):
    """Format bytes into human-readable strings (KB, MB, GB)."""
    try:
        bytes_value = float(value)
    except (ValueError, TypeError):
        return "0 bytes"
    
    for unit in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"

# --- Date & Deadline Filters ---

@register.filter
def is_nearing_deadline(order):
    """True if order deadline is within 24 hours."""
    if not order or not hasattr(order, 'deadline') or not order.deadline:
        return False
    time_left = order.deadline - timezone.now()
    return 0 <= time_left.total_seconds() <= 86400

@register.filter
def days_until(value):
    """Returns number of days until a future date."""
    if not value:
        return None
    delta = value - timezone.now().date()
    return delta.days

# --- Complex Inclusion Tags & Progress ---

@register.simple_tag
def get_verification_progress(verification):
    """Returns progress percentage for verification progress bar."""
    stages = {
        'registered': 10,
        'profile_completed': 30,
        'documents_submitted': 50,
        'under_admin_review': 75,
        'approved': 100,
        'rejected': 100,
        'revision_required': 40,
    }
    return stages.get(verification.state, 0)

@register.inclusion_tag('accounts/partials/verification_timeline.html')
def verification_timeline(verification):
    """Renders a structured timeline list for the user UI."""
    timeline = []
    
    # Base Event: Registration
    timeline.append({
        'event': 'Registered',
        'date': verification.created_at,
        'completed': True,
        'icon': 'fa-user-plus',
    })
    
    if verification.profile_completed_at:
        timeline.append({
            'event': 'Profile Completed',
            'date': verification.profile_completed_at,
            'completed': True,
            'icon': 'fa-user-check',
        })
        
    if verification.documents_submitted_at:
        timeline.append({
            'event': 'Documents Submitted',
            'date': verification.documents_submitted_at,
            'completed': True,
            'icon': 'fa-file-upload',
        })
    
    if verification.state == 'approved':
        timeline.append({
            'event': 'Verified',
            'date': verification.review_completed_at,
            'completed': True,
            'icon': 'fa-check-circle',
        })
        
    return {'timeline': timeline}

@register.inclusion_tag('accounts/partials/document_status.html')
def document_status_badge(document):
    """Context for document status badge partial."""
    return {'document': document}