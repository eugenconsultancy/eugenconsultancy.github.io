from django.urls import path
from . import views

urlpatterns = [
    path('', views.teacher_list, name='teacher_list'),
    path('create/', views.teacher_create, name='teacher_create'),
    path('<int:pk>/', views.teacher_detail, name='teacher_detail'),
    path('<int:pk>/update/', views.teacher_update, name='teacher_update'),
    path('my-students/', views.teacher_students, name='teacher_students'),
    # ADD THIS: For admin to view all teacher passwords
    path('passwords/', views.teacher_passwords_view, name='teacher_passwords_view'),
]