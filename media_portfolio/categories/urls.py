from django.urls import path
from . import views

app_name = 'categories'

urlpatterns = [
    path('', views.CategoryListView.as_view(), name='list'),
    path('<slug:slug>/', views.CategoryDetailView.as_view(), name='detail'),
]