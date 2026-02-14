from django import template
from django.utils import timezone
from django.db.models import Count, Q
from django.core.cache import cache
from ..models import Comment

register = template.Library()


@register.filter
def days_since(value):
    """
    Return human-readable time since a date.
    Usage: {{ comment.created_at|days_since }}
    """
    if not value:
        return ''
    
    delta = timezone.now() - value
    seconds = delta.total_seconds()
    
    if seconds < 60:
        return 'just now'
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f'{minutes} minute' + ('s' if minutes > 1 else '') + ' ago'
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f'{hours} hour' + ('s' if hours > 1 else '') + ' ago'
    elif seconds < 604800:  # 7 days
        days = int(seconds // 86400)
        if days == 0:
            return 'today'
        elif days == 1:
            return 'yesterday'
        else:
            return f'{days} days ago'
    elif seconds < 2592000:  # 30 days
        weeks = int(seconds // 604800)
        return f'{weeks} week' + ('s' if weeks > 1 else '') + ' ago'
    elif seconds < 31536000:  # 365 days
        months = int(seconds // 2592000)
        return f'{months} month' + ('s' if months > 1 else '') + ' ago'
    else:
        years = int(seconds // 31536000)
        return f'{years} year' + ('s' if years > 1 else '') + ' ago'


@register.simple_tag
def get_comment_count(media_item, include_replies=False):
    """
    Get count of approved comments for a media item.
    
    Args:
        media_item: The media item object
        include_replies: If True, counts all comments including replies
                        If False, counts only top-level comments
    """
    queryset = Comment.objects.filter(
        media_item=media_item,
        is_approved=True
    )
    
    if not include_replies:
        queryset = queryset.filter(parent__isnull=True)
    
    return queryset.count()


@register.simple_tag
def get_recent_comments(limit=5, media_type=None):
    """
    Get most recent approved comments with optional media type filter.
    
    Args:
        limit: Maximum number of comments to return
        media_type: Optional filter by 'image' or 'video'
    """
    queryset = Comment.objects.filter(
        is_approved=True
    ).select_related('media_item')
    
    if media_type:
        queryset = queryset.filter(media_item__media_type=media_type)
    
    return queryset.order_by('-created_at')[:limit]


@register.simple_tag
def get_featured_comments(limit=3):
    """
    Get featured comments/testimonials.
    """
    return Comment.objects.filter(
        is_approved=True,
        is_featured=True
    ).select_related('media_item')[:limit]


@register.simple_tag
def get_user_comments(user, limit=None):
    """
    Get comments by a specific user (by email).
    """
    queryset = Comment.objects.filter(
        email=user.email if hasattr(user, 'email') else user,
        is_approved=True
    ).order_by('-created_at')
    
    if limit:
        queryset = queryset[:limit]
    
    return queryset


@register.simple_tag
def get_comment_stats(media_item=None):
    """
    Get comment statistics, optionally filtered by media item.
    Returns dictionary with counts.
    """
    cache_key = f'comment_stats_{media_item.id if media_item else "global"}'
    stats = cache.get(cache_key)
    
    if stats is None:
        queryset = Comment.objects.all()
        if media_item:
            queryset = queryset.filter(media_item=media_item)
        
        stats = queryset.aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(is_approved=True)),
            featured=Count('id', filter=Q(is_featured=True)),
            spam=Count('id', filter=Q(is_spam=True))
        )
        
        # Cache for 5 minutes
        cache.set(cache_key, stats, 300)
    
    return stats


@register.inclusion_tag('comments/comment_tree.html', takes_context=True)
def render_comment_tree(context, comments, media_item=None):
    """
    Render a tree of comments with replies.
    
    Args:
        comments: QuerySet or list of comments
        media_item: Optional media item for reply form
    """
    # Prefetch replies for efficiency
    if hasattr(comments, 'prefetch_related'):
        comments = comments.prefetch_related('replies')
    
    return {
        'comments': comments,
        'media_item': media_item or context.get('media_item'),
        'user': context.get('user'),
        'request': context.get('request')
    }


@register.inclusion_tag('comments/comment_form.html')
def render_comment_form(media_item, user=None):
    """
    Render comment form for a media item.
    """
    return {
        'media_item': media_item,
        'user': user,
        'can_comment': True  # Add your permission logic here
    }


@register.filter
def comment_depth(comment):
    """
    Get the depth of a comment in the thread.
    Useful for styling nested comments.
    """
    depth = 0
    current = comment
    while current.parent:
        depth += 1
        current = current.parent
        if depth > 10:  # Prevent infinite loops
            break
    return depth


@register.simple_tag
def can_moderate_comment(user, comment):
    """
    Check if user can moderate a comment.
    """
    if not user.is_authenticated:
        return False
    
    if user.is_staff or user.is_superuser:
        return True
    
    # Add custom moderation permissions here
    return False


@register.filter
def truncate_comment(content, words=30):
    """
    Truncate comment content to specified number of words.
    """
    if not content:
        return ''
    
    words_list = content.split()
    if len(words_list) <= words:
        return content
    
    truncated = ' '.join(words_list[:words])
    return truncated + '...'


@register.simple_tag
def get_comment_replies_count(comment):
    """
    Get count of replies for a comment.
    """
    return comment.replies.filter(is_approved=True).count()