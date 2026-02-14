from django.views.generic import ListView, TemplateView
from django.core.cache import cache
from .models import BlogPost


class BlogListView(ListView):
    """
    View for listing blog posts
    """
    model = BlogPost
    template_name = 'blog/blog_list.html'
    context_object_name = 'posts'
    paginate_by = 9

    def get_queryset(self):
        return BlogPost.objects.filter(
            is_published=True
        ).order_by('-published_at')


class LatestPostsView(TemplateView):
    """
    View for latest posts widget (for homepage)
    """
    template_name = 'blog/latest_posts_widget.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Try to get from cache
        posts = cache.get('latest_blog_posts')
        
        if posts is None:
            posts = BlogPost.objects.filter(
                is_published=True
            ).order_by('-published_at')[:5]
            
            # Cache for 1 hour
            cache.set('latest_blog_posts', posts, 3600)
        
        context['posts'] = posts
        return context