from django.shortcuts import render
from django.views.generic import TemplateView, ListView
from django.http import HttpResponse, JsonResponse
from media_portfolio.media.models import MediaItem
from media_portfolio.categories.models import Category
from media_portfolio.comments.models import Testimonial
from django.db import models
from django.views.generic import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt


class HomeView(TemplateView):
    """
    Homepage view with featured content
    """
    template_name = 'core/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get featured media
        context['featured_media'] = MediaItem.objects.filter(
            is_published=True,
            featured=True
        ).select_related().prefetch_related('categories')[:12]
        
        # Get recent media
        context['recent_media'] = MediaItem.objects.filter(
            is_published=True
        ).select_related().prefetch_related('categories')[:8]
        
        # Get categories with counts
        context['categories'] = Category.objects.filter(
            is_active=True
        ).annotate(
            media_count=models.Count('media_items')
        )[:10]
        
        # Get featured testimonials
        context['testimonials'] = Testimonial.objects.filter(
            featured=True
        )[:6]
        
        # Get statistics
        context['total_media'] = MediaItem.objects.filter(is_published=True).count()
        context['total_categories'] = Category.objects.filter(is_active=True).count()
        context['total_videos'] = MediaItem.objects.filter(
            is_published=True, 
            media_type='video'
        ).count()
        context['total_images'] = MediaItem.objects.filter(
            is_published=True, 
            media_type='image'
        ).count()
        
        return context


class AboutView(TemplateView):
    """
    About page view
    """
    template_name = 'core/about.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get some featured work for the about page
        context['featured_work'] = MediaItem.objects.filter(
            is_published=True,
            featured=True
        )[:6]
        
        return context


class PrivacyPolicyView(TemplateView):
    """
    Privacy policy page
    """
    template_name = 'core/privacy.html'


class TermsOfServiceView(TemplateView):
    """
    Terms of service page
    """
    template_name = 'core/terms.html'


class SitemapView(TemplateView):
    """
    XML sitemap for search engines
    """
    template_name = 'core/sitemap.xml'
    content_type = 'application/xml'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all published media
        context['media_items'] = MediaItem.objects.filter(is_published=True)
        
        # Get all active categories
        context['categories'] = Category.objects.filter(is_active=True)
        
        # Get all published collections
        from media_portfolio.collections.models import Collection
        context['collections'] = Collection.objects.filter(is_published=True)
        
        return context


class RobotsTxtView(TemplateView):
    """
    robots.txt for search engine crawling instructions
    """
    template_name = 'core/robots.txt'
    content_type = 'text/plain'

@method_decorator(csrf_exempt, name='dispatch')
class SetThemeView(View):
    """
    View for setting theme preference
    """
    
    def post(self, request):
        theme = request.POST.get('theme', 'system')
        
        if theme in ['light', 'dark', 'system']:
            request.session['theme'] = theme
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'theme': theme
                })
        
        return JsonResponse({
            'success': False,
            'error': 'Invalid theme'
        }, status=400)