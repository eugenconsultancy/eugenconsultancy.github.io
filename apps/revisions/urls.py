"""
URL configuration for revisions app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import RevisionRequestViewSet, RevisionCycleViewSet

router = DefaultRouter()
router.register(r'requests', RevisionRequestViewSet, basename='revision-request')
router.register(r'cycles', RevisionCycleViewSet, basename='revision-cycle')

urlpatterns = [
    path('', include(router.urls)),
]