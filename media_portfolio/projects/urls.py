from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.ProjectListView.as_view(), name='list'),
    path('featured/', views.FeaturedProjectsView.as_view(), name='featured'),
    path('difficulty/<str:level>/', views.ProjectsByDifficultyView.as_view(), name='by_difficulty'),
    path('<slug:slug>/', views.ProjectDetailView.as_view(), name='detail'),
    path('<slug:slug>/like/', views.LikeProjectView.as_view(), name='like'),
    path('<slug:slug>/comment/', views.AddCommentView.as_view(), name='add_comment'),
    path('<slug:slug>/load-comments/', views.LoadCommentsView.as_view(), name='load_comments'),
]