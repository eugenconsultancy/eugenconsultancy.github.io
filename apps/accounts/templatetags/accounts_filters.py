from django import template
from django.utils import timezone

register = template.Library()

@register.filter
def state_color(state):
    """Return Bootstrap color class for state."""
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
def document_icon(document_type):
    """Return icon class for document type."""
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
    """Return CSS class for document icon."""
    class_map = {
        'id_proof': 'id',
        'degree_certificate': 'certificate',
        'transcript': 'word',
        'cv': 'pdf',
        'portfolio': 'pdf',
        'other': 'word',
    }
    return class_map.get(document_type, 'word')

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

@register.filter
def split(value, delimiter=','):
    """Split string by delimiter."""
    return value.split(delimiter) if value else []

@register.filter
def strip(value):
    """Strip whitespace from string."""
    return value.strip()

@register.filter
def subtract(value, arg):
    """Subtract arg from value."""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def filesizeformat(value):
    """Format file size in human readable format."""
    if value is None:
        return "0 bytes"
    
    try:
        bytes_value = int(value)
    except (ValueError, TypeError):
        return value
    
    if bytes_value < 1024:
        return f"{bytes_value} bytes"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value / 1024:.1f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_value / (1024 * 1024 * 1024):.1f} GB"

@register.filter
def is_nearing_deadline(order):
    """Check if order deadline is within 24 hours."""
    if not order.deadline:
        return False
    time_left = order.deadline - timezone.now()
    return time_left.total_seconds() <= 24 * 60 * 60

@register.filter
def days_until(value):
    """Calculate days until given date."""
    if not value:
        return None
    delta = value - timezone.now().date()
    return delta.days

@register.filter
def verification_stage_color(stage):
    """Return color for verification stage."""
    color_map = {
        'started': 'info',
        'profile_completed': 'primary',
        'documents_submitted': 'warning',
        'under_review': 'warning',
        'approved': 'success',
        'rejected': 'danger',
        'revision_required': 'warning',
    }
    return color_map.get(stage, 'secondary')

@register.simple_tag
def get_verification_progress(verification):
    """Calculate verification progress percentage."""
    stages = {
        'registered': 0,
        'profile_completed': 25,
        'documents_submitted': 50,
        'under_admin_review': 75,
        'approved': 100,
        'rejected': 0,
        'revision_required': 50,
    }
    return stages.get(verification.state, 0)

@register.inclusion_tag('accounts/partials/verification_timeline.html')
def verification_timeline(verification):
    """Render verification timeline."""
    timeline = []
    
    # Registration
    timeline.append({
        'event': 'Registered',
        'date': verification.created_at,
        'completed': True,
        'current': False,
        'icon': 'fa-user-plus',
    })
    
    # Profile completion
    if verification.profile_completed_at:
        timeline.append({
            'event': 'Profile Completed',
            'date': verification.profile_completed_at,
            'completed': True,
            'current': False,
            'icon': 'fa-user-check',
        })
    elif verification.state in ['profile_completed', 'documents_submitted', 'under_admin_review', 'revision_required']:
        timeline.append({
            'event': 'Profile Completion',
            'date': None,
            'completed': False,
            'current': True,
            'icon': 'fa-user-edit',
        })
    
    # Documents submission
    if verification.documents_submitted_at:
        timeline.append({
            'event': 'Documents Submitted',
            'date': verification.documents_submitted_at,
            'completed': True,
            'current': False,
            'icon': 'fa-file-upload',
        })
    elif verification.state in ['documents_submitted', 'under_admin_review', 'revision_required']:
        timeline.append({
            'event': 'Document Submission',
            'date': None,
            'completed': False,
            'current': True,
            'icon': 'fa-file-upload',
        })
    
    # Admin review
    if verification.review_started_at:
        timeline.append({
            'event': 'Under Admin Review',
            'date': verification.review_started_at,
            'completed': verification.review_completed_at is not None,
            'current': verification.state == 'under_admin_review',
            'icon': 'fa-search',
        })
    
    # Completion
    if verification.review_completed_at:
        timeline.append({
            'event': verification.get_state_display(),
            'date': verification.review_completed_at,
            'completed': True,
            'current': False,
            'icon': 'fa-check-circle' if verification.state == 'approved' else 'fa-times-circle',
        })
    
    return {'timeline': timeline}

@register.inclusion_tag('accounts/partials/document_status.html')
def document_status_badge(document):
    """Render document status badge."""
    return {'document': document}