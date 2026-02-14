from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.core.paginator import Paginator
from .models import Collection


class CollectionListView(ListView):
    """
    View for listing all collections
    """
    model = Collection
    template_name = 'collections/collection_list.html'
    context_object_name = 'collections'
    paginate_by = 12

    def get_queryset(self):
        return Collection.objects.filter(
            is_published=True
        ).prefetch_related('media_items')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Group collections by type for filtering
        collection_types = Collection.objects.filter(
            is_published=True
        ).values_list('collection_type', flat=True).distinct()
        
        context['collection_types'] = [(t, dict(Collection.COLLECTION_TYPES).get(t, t)) 
                                       for t in collection_types]
        
        # Featured collections
        context['featured_collections'] = Collection.objects.filter(
            is_published=True,
            featured=True
        )[:3]
        
        return context


class CollectionDetailView(DetailView):
    """
    View for displaying a single collection
    """
    model = Collection
    template_name = 'collections/collection_detail.html'
    context_object_name = 'collection'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Collection.objects.filter(
            is_published=True
        ).prefetch_related('media_items')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get collection items with ordering
        collection_items = self.object.collectionitem_set.select_related(
            'media_item'
        ).order_by('order')
        
        context['collection_items'] = collection_items
        
        # Related collections (same type)
        context['related_collections'] = Collection.objects.filter(
            is_published=True,
            collection_type=self.object.collection_type
        ).exclude(
            id=self.object.id
        )[:3]
        
        return context