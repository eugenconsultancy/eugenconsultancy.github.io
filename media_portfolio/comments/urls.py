from django.urls import path
from . import views

app_name = 'comments'

urlpatterns = [
    path('add/<int:media_id>/', views.AddCommentView.as_view(), name='add'),
    path('load/<int:media_id>/', views.LoadCommentsView.as_view(), name='load'),
    path('moderate/<int:comment_id>/', views.ModerateCommentView.as_view(), name='moderate'),
]