from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from media_portfolio.core.views import SetThemeView  # Add this import

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('media_portfolio.core.urls')),
    path('media/', include('media_portfolio.media.urls')),
    path('categories/', include('media_portfolio.categories.urls')),
    path('collections/', include('media_portfolio.collections.urls')),
    path('inquiries/', include('media_portfolio.inquiries.urls')),
    path('projects/', include('media_portfolio.projects.urls')),  # Add this
    path('blog/', include('media_portfolio.blog.urls')),  # Add this
    
    # Theme API
    path('set-theme/', SetThemeView.as_view(), name='set_theme'),  # Add this
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)