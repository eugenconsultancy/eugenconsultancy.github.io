from django.urls import path
from . import views

urlpatterns = [
    # Subject management (admin only)
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/create/', views.subject_create, name='subject_create'),
    
    # Marks management
    path('', views.mark_list, name='mark_list'),
    path('create/', views.mark_create, name='mark_create'),
    path('<int:pk>/update/', views.mark_update, name='mark_update'),
    
    # Student results
    path('results/', views.student_results, name='student_results'),
    
    # Reports
    path('reports/create/', views.student_report_create, name='report_create'),

     # Analytics and trends
    path('analytics/student-performance/', views.student_performance_analytics, name='student_performance_analytics'),
    path('analytics/student/<int:student_id>/', views.student_performance_detail, name='student_performance_detail'),
    path('analytics/term-comparison/', views.term_comparison_analytics, name='term_comparison_analytics'),
    path('analytics/generate-trends/', views.generate_performance_trends, name='generate_performance_trends'),
]