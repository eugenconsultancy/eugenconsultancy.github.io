from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.BlogListView.as_view(), name='list'),
    path('latest/', views.LatestPostsView.as_view(), name='latest'),
]