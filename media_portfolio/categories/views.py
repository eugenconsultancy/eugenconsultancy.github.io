from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from .models import Category
from media_portfolio.media.models import MediaItem
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger



class CategoryListView(ListView):
    """
    View for listing all categories grouped by type
    """
    model = Category
    template_name = 'categories/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.filter(is_active=True).prefetch_related('media_items')


class CategoryDetailView(DetailView):
    """
    View for displaying a single category and its media
    """
    model = Category
    template_name = 'categories/category_detail.html'
    context_object_name = 'category'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.object
        
        # Get media items in this category
        media_items = MediaItem.objects.filter(
            is_published=True,
            categories=category
        ).select_related().prefetch_related('categories')
        
        # Paginate
        paginator = Paginator(media_items, 12)
        page = self.request.GET.get('page')
        
        try:
            media_items = paginator.page(page)
        except PageNotAnInteger:
            media_items = paginator.page(1)
        except EmptyPage:
            media_items = paginator.page(paginator.num_pages)
        
        context['media_items'] = media_items
        context['is_paginated'] = media_items.has_other_pages()
        
        return context