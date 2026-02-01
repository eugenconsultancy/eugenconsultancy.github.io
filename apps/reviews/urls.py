# apps/reviews/urls.py

from django.urls import path, include
from . import views

app_name = 'reviews'

urlpatterns = [
    # Customer review URLs
    path(
        'order/<uuid:order_id>/create/',
        views.CreateReviewView.as_view(),
        name='create'
    ),
    path(
        'review/<uuid:review_id>/',
        views.ReviewDetailView.as_view(),
        name='view'
    ),
    
    # Add this to your reviews URLs
    path('select-order/', views.SelectOrderForReviewView.as_view(), name='select_order'),
    # Review response URLs
    path(
        'review/<uuid:review_id>/response/create/',
        views.CreateReviewResponseView.as_view(),
        name='create_response'
    ),
    
    # Flag review (AJAX endpoint)
    path(
        'review/<uuid:review_id>/flag/',
        views.flag_review,
        name='flag'
    ),
    
    # Writer review URLs
    path(
        'writer/my-reviews/',
        views.WriterReviewsView.as_view(),
        name='writer_reviews'
    ),
    path(
        'writer/performance/',
        views.writer_performance_report,
        name='writer_performance'
    ),
    
    # Admin moderation URLs
    path(
        'admin/moderation/',
        views.ModerationQueueView.as_view(),
        name='moderation_queue'
    ),
    path(
        'review/<uuid:review_id>/moderate/<str:action>/',
        views.moderate_review,
        name='moderate_review'
    ),
    path(
        'admin/analytics/',
        views.review_analytics,
        name='analytics'
    ),
]