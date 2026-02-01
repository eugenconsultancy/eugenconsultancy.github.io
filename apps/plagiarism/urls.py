"""
URL configuration for plagiarism app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PlagiarismCheckViewSet,
    PlagiarismReportViewSet,
    PlagiarismPolicyViewSet
)

router = DefaultRouter()
router.register(r'checks', PlagiarismCheckViewSet, basename='plagiarism-check')
router.register(r'reports', PlagiarismReportViewSet, basename='plagiarism-report')
router.register(r'policies', PlagiarismPolicyViewSet, basename='plagiarism-policy')

urlpatterns = [
    path('api/', include(router.urls)),
]