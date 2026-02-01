"""
Template filters for orders app.
"""
from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()


@register.filter
def state_bg_color(state):
    """Get Bootstrap color class for order state."""
    color_map = {
        'draft': 'secondary',
        'paid': 'info',
        'assigned': 'primary',
        'in_progress': 'warning',
        'delivered': 'success',
        'revision_requested': 'warning',
        'in_revision': 'warning',
        'completed': 'success',
        'disputed': 'danger',
        'refunded': 'secondary',
        'cancelled': 'secondary',
    }
    return color_map.get(state, 'secondary')


@register.filter
def urgency_bg_color(urgency):
    """Get Bootstrap color class for urgency level."""
    color_map = {
        'standard': 'secondary',
        'urgent': 'warning',
        'very_urgent': 'danger',
        'emergency': 'danger',
    }
    return color_map.get(urgency, 'secondary')


@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key."""
    return dictionary.get(key)


@register.filter
def format_currency(value):
    """Format value as currency."""
    if value is None:
        return '$0.00'
    return f'${value:,.2f}'


@register.filter
def humanize_timedelta(timedelta_obj):
    """Convert timedelta to human-readable format."""
    if not timedelta_obj:
        return 'N/A'
    
    days = timedelta_obj.days
    seconds = timedelta_obj.seconds
    
    if days > 0:
        return f'{days}d {seconds // 3600}h left'
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            return f'{hours}h {minutes}m left'
        else:
            return f'{minutes}m left'


@register.filter
def is_overdue(deadline):
    """Check if deadline is overdue."""
    if not deadline:
        return False
    return timezone.now() > deadline


@register.filter
def time_remaining(deadline):
    """Calculate time remaining until deadline."""
    if not deadline:
        return timedelta(0)
    
    remaining = deadline - timezone.now()
    return max(remaining, timedelta(0))


@register.filter
def progress_width(order):
    """Calculate progress bar width based on order state."""
    progress_map = {
        'draft': 0,
        'paid': 10,
        'assigned': 20,
        'in_progress': 40,
        'delivered': 80,
        'revision_requested': 85,
        'in_revision': 90,
        'completed': 100,
        'disputed': 50,
        'refunded': 100,
        'cancelled': 100,
    }
    return progress_map.get(order.state, 0)


@register.filter
def can_request_revision(order):
    """Check if client can request revision."""
    return (
        order.state == 'delivered' and
        order.revision_count < order.max_revisions
    )


@register.filter
def can_be_assigned(order):
    """Check if order can be assigned to a writer."""
    return (
        order.state == 'paid' and
        not order.writer
    )


@register.filter
def format_file_size(bytes_value):
    """Format file size in human-readable format."""
    if bytes_value is None:
        return 'N/A'
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} TB"


@register.filter
def truncate_chars(value, length):
    """Truncate string to specified length."""
    if not value:
        return ''
    if len(value) <= length:
        return value
    return value[:length] + '...'


@register.filter
def get_state_display(order, state_code=None):
    """Get display name for order state."""
    if state_code:
        # Get from STATE_CHOICES
        for code, name in order.STATE_CHOICES:
            if code == state_code:
                return name
        return state_code
    return order.get_state_display()


@register.filter
def get_academic_level_display(order, level_code=None):
    """Get display name for academic level."""
    if level_code:
        # Get from AcademicLevel choices
        for code, name in order.AcademicLevel.choices:
            if code == level_code:
                return name
        return level_code
    return order.get_academic_level_display()


@register.filter
def get_urgency_display(order, urgency_code=None):
    """Get display name for urgency level."""
    if urgency_code:
        # Get from UrgencyLevel choices
        for code, name in order.UrgencyLevel.choices:
            if code == urgency_code:
                return name
        return urgency_code
    return order.get_urgency_display()


@register.filter
def calculate_writer_payment(order):
    """Calculate writer payment amount."""
    if hasattr(order, 'writer_payment') and order.writer_payment:
        return order.writer_payment
    # Calculate if not set
    platform_fee_percentage = 20  # 20% platform fee
    writer_percentage = 100 - platform_fee_percentage
    return order.price * writer_percentage / 100


@register.filter
def calculate_platform_fee(order):
    """Calculate platform fee amount."""
    if hasattr(order, 'platform_fee') and order.platform_fee:
        return order.platform_fee
    # Calculate if not set
    platform_fee_percentage = 20  # 20% platform fee
    return order.price * platform_fee_percentage / 100


@register.simple_tag
def get_time_ago(datetime_obj):
    """Get time ago in human readable format."""
    if not datetime_obj:
        return 'N/A'
    
    now = timezone.now()
    diff = now - datetime_obj
    
    if diff.days > 365:
        years = diff.days // 365
        return f'{years} year{"s" if years > 1 else ""} ago'
    elif diff.days > 30:
        months = diff.days // 30
        return f'{months} month{"s" if months > 1 else ""} ago'
    elif diff.days > 0:
        return f'{diff.days} day{"s" if diff.days > 1 else ""} ago'
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f'{hours} hour{"s" if hours > 1 else ""} ago'
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f'{minutes} minute{"s" if minutes > 1 else ""} ago'
    else:
        return 'just now'