"""
URL configuration for disputes app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DisputeViewSet,
    DisputeEvidenceViewSet,
    DisputeMessageViewSet
)

router = DefaultRouter()
router.register(r'', DisputeViewSet, basename='dispute')
router.register(r'evidence', DisputeEvidenceViewSet, basename='dispute-evidence')
router.register(r'messages', DisputeMessageViewSet, basename='dispute-message')

urlpatterns = [
    path('api/', include(router.urls)),
]