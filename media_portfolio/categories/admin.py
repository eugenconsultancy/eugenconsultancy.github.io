from django.contrib import admin
from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'parent', 'get_media_count', 'sort_order', 'is_active']
    list_filter = ['category_type', 'is_active', 'parent']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['sort_order', 'is_active']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'category_type', 'parent', 'description')
        }),
        ('Visual', {
            'fields': ('cover_image', 'icon', 'sort_order', 'is_active')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
    )
    
    def get_media_count(self, obj):
        """Return the number of media items in this category"""
        return obj.media_items.count()
    get_media_count.short_description = 'Media Count'