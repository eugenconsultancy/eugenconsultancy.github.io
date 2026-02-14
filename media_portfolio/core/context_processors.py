from .models import SiteSettings
from media_portfolio.blog.models import BlogPost
from media_portfolio.projects.models import Project

def site_settings(request):
    """Add site settings to all templates"""
    try:
        settings = SiteSettings.objects.first()
    except:
        settings = None
    
    return {
        'site_settings': settings
    }

def theme_preference(request):
    """Add theme preference to templates"""
    theme = request.session.get('theme', 'system')
    return {
        'theme_preference': theme
    }

def global_stats(request):
    """Add global stats to all templates"""
    from media_portfolio.media.models import MediaItem
    from media_portfolio.projects.models import Project
    from media_portfolio.blog.models import BlogPost
    
    return {
        'total_projects': Project.objects.filter(is_published=True).count(),
        'total_media': MediaItem.objects.filter(is_published=True).count(),
        'total_blog_posts': BlogPost.objects.filter(is_published=True).count(),
    }

def latest_blog_posts(request):
    """Add latest blog posts to all templates"""
    posts = BlogPost.objects.filter(is_published=True).order_by('-published_at')[:3]
    return {
        'latest_blog_posts': posts
    }