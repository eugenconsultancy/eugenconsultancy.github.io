"""
API v1 URL configuration.
"""
from django.urls import path, include, re_path
from rest_framework import permissions
from rest_framework.routers import DefaultRouter
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Import viewsets
from .accounts.views import UserViewSet, WriterProfileViewSet
from .orders.views import OrderViewSet
from .payments.views import PaymentViewSet
# from .revisions.views import RevisionRequestViewSet
# from .plagiarism.views import PlagiarismCheckViewSet
from apps.disputes.views import DisputeViewSet, DisputeEvidenceViewSet

# === SWAGGER CONFIGURATION ===
schema_view = get_schema_view(
   openapi.Info(
      title="EBWriting API",
      default_version='v1',
      description="Academic Platform API Documentation",
      terms_of_service="https://www.ebwriting.com/terms/",
      contact=openapi.Contact(email="support@ebwriting.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

# Create router
router = DefaultRouter()

# Accounts endpoints
router.register(r'users', UserViewSet, basename='user')
router.register(r'writer-profiles', WriterProfileViewSet, basename='writer-profile')

# Orders endpoints
router.register(r'orders', OrderViewSet, basename='order')

# Payments endpoints
router.register(r'payments', PaymentViewSet, basename='payment')

# Revisions endpoints
# router.register(r'revisions', RevisionRequestViewSet, basename='revision')

# Plagiarism endpoints (admin only)
# router.register(r'plagiarism-checks', PlagiarismCheckViewSet, basename='plagiarism-check')

# Disputes endpoints
router.register(r'disputes', DisputeViewSet, basename='dispute')
router.register(r'dispute-evidence', DisputeEvidenceViewSet, basename='dispute-evidence')

# URL Patterns
urlpatterns = [
    path('', include(router.urls)),
    
    # Authentication endpoints
    path('auth/', include('rest_framework.urls')),
    path('auth/token/', include('djoser.urls.authtoken')),
    
    # Health check endpoint
    path('health/', include('health_check.urls')),
    
    # === API DOCUMENTATION ===
    # Swagger UI
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    # ReDoc UI
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    # Plain JSON/YAML schemas
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
]