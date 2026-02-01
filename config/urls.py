"""
Main URL configuration for EBWriting Platform.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # ===== ADMIN =====
    path('admin/', admin.site.urls),
    
    # ===== PHASE 1: FOUNDATION, COMPLIANCE & TRUST =====
    # Authentication & Accounts
    path('accounts/', include('apps.accounts.urls')),
    path('accounts/', include('allauth.urls')),  # Django Allauth
    
    # Core Platform
    path('orders/', include('apps.orders.urls')),
    path('payments/', include('apps.payments.urls')),
    path('compliance/', include('apps.compliance.urls')),
    
    # Admin Tools
    path('admin-tools/', include('apps.admin_tools.urls')),
    
    # ===== PHASE 2: COMMUNICATION & DELIVERY CONTROL =====
    # Communication
    path('messaging/', include('apps.messaging.urls')),
    path('notifications/', include('apps.notifications.urls')),
    
    # Document Management
    path('documents/', include('apps.documents.urls')),
    
    # ===== PHASE 3: QUALITY, DISPUTES & API FOUNDATION =====
    # Quality Control
    path('revisions/', include('apps.revisions.urls')),
    path('plagiarism/', include('apps.plagiarism.urls')),
    path('disputes/', include('apps.disputes.urls')),
    
    # API
    path('api/', include('apps.api.urls')),
    
    # ===== PHASE 4: WRITER ECONOMY & ANALYTICS =====
    # Financial
    path('wallet/', include('apps.wallet.urls')),
    
    # Feedback & Reviews
    path('reviews/', include('apps.reviews.urls')),
    
    # Analytics & Reporting
    path('analytics/', include('apps.analytics.urls')),
    
    # ===== PHASE 5: SEO & ASSISTIVE AI =====
    # Blog & SEO Content
    path('blog/', include('apps.blog.urls', namespace='blog')),
    
    # AI Writing Assistants
    path('ai-tools/', include('apps.ai_tools.urls', namespace='ai_tools')),
    
    # ===== SYSTEM PAGES =====
    # Home page
    path('', TemplateView.as_view(template_name='base/home.html'), name='home'),
    
    # Dashboard (authenticated users)
    path('dashboard/', TemplateView.as_view(template_name='accounts/dashboard.html'), name='dashboard'),
    
    # Health check
    path('health/', TemplateView.as_view(template_name='health.html'), name='simple_health_check'),
    
    # Legal pages
    path('terms/', TemplateView.as_view(template_name='legal/terms.html'), name='terms'),
    path('privacy/', TemplateView.as_view(template_name='legal/privacy.html'), name='privacy'),
    path('acceptable-use/', TemplateView.as_view(template_name='legal/acceptable_use.html'), name='acceptable_use'),
]

# ===== API DOCUMENTATION =====
if settings.DEBUG:
    # Swagger/OpenAPI documentation
    from rest_framework import permissions
    from drf_yasg.views import get_schema_view
    from drf_yasg import openapi
    
    schema_view = get_schema_view(
        openapi.Info(
            title="EBWriting API",
            default_version='v1',
            description="EBWriting Academic Platform API",
            terms_of_service="https://ebwriting.com/terms/",
            contact=openapi.Contact(email="api@ebwriting.com"),
            license=openapi.License(name="Commercial License"),
        ),
        public=True,
        permission_classes=(permissions.AllowAny,),
    )
    
    urlpatterns += [
        path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='api-docs'),
        path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='api-redoc'),
    ]

# ===== STATIC & MEDIA FILES =====
# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# ===== DEBUG TOOLBAR =====
if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

# # ===== ERROR HANDLERS =====
# handler400 = 'config.views.handler400'
# handler403 = 'config.views.handler403'
# handler404 = 'config.views.handler404'
# handler500 = 'config.views.handler500'

# ===== ADMIN CUSTOMIZATION =====
admin.site.site_header = 'EBWriting Admin'
admin.site.site_title = 'EBWriting Platform'
admin.site.index_title = 'Dashboard'