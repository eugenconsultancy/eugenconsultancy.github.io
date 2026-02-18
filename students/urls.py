from django.urls import path
from . import views

urlpatterns = [
    path('', views.student_list, name='student_list'),
    path('profile/', views.student_profile, name='student_profile'),
    path('create/', views.student_create, name='student_create'),
    path('<int:pk>/', views.student_detail, name='student_detail'),
    path('<int:pk>/update/', views.student_update, name='student_update'),
    # ADD THIS: For teachers to view their students' passwords
    path('teacher-view/', views.teacher_student_list, name='teacher_student_list'),
]