from django.contrib import admin
from django.utils.html import format_html
from .models import Collection, CollectionItem


class CollectionItemInline(admin.TabularInline):
    model = CollectionItem
    extra = 5
    ordering = ['order']
    fields = ['media_item', 'order', 'custom_caption']
    autocomplete_fields = ['media_item']


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'collection_type', 'featured', 'is_published', 'media_count', 'created_at']
    list_filter = ['collection_type', 'featured', 'is_published', 'layout']
    search_fields = ['title', 'description']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [CollectionItemInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'collection_type', 'description')
        }),
        ('Media', {
            'fields': ('cover_image',)
        }),
        ('Display', {
            'fields': ('layout', 'featured', 'is_published', 'published_date', 'sort_order')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
    )
    
    def media_count(self, obj):
        return obj.media_items.count()
    media_count.short_description = 'Items'
    
    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px;" />',
                obj.cover_image.url
            )
        return "No cover"
    cover_preview.short_description = 'Cover'