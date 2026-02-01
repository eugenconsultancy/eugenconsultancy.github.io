"""
Main API URL configuration.
"""
from django.urls import path, include
from rest_framework.schemas import get_schema_view
from rest_framework.documentation import include_docs_urls
from drf_yasg.views import get_schema_view as yasg_schema_view
from drf_yasg import openapi
from rest_framework import permissions

# Swagger/OpenAPI schema view
schema_view = yasg_schema_view(
    openapi.Info(
        title="EBWriting Platform API",
        default_version='v1',
        description="API documentation for EBWriting Academic Platform",
        terms_of_service="https://ebwriting.com/terms/",
        contact=openapi.Contact(email="api@ebwriting.com"),
        license=openapi.License(name="Proprietary License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # API v1
    path('v1/', include('apps.api.v1.urls')),
    
    # API Documentation
    path('docs/', include_docs_urls(title='EBWriting API')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # Health check
    path('api-health/', include('health_check.urls')),
]