from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.AnalyticsDashboardView.as_view(), name='dashboard'),
    
    # KPIs
    path('kpis/', views.KPIListView.as_view(), name='kpi_list'),
    path('kpis/<slug:slug>/', views.KPIDetailView.as_view(), name='kpi_detail'),
    path('api/kpi/<slug:kpi_slug>/calculate/', views.calculate_kpi_api, name='calculate_kpi'),
    
    # Reports
    path('reports/', views.ReportListView.as_view(), name='report_list'),
    path('reports/<uuid:pk>/', views.ReportDetailView.as_view(), name='report_detail'),
    path('api/reports/<uuid:report_id>/generate/', views.generate_report_api, name='generate_report'),
    path('reports/download/<uuid:execution_id>/', views.download_report, name='download_report'),
    
    # Performance Reports
    path('performance/', views.PerformanceReportView.as_view(), name='performance_report'),
    path('performance/export/', views.export_performance_report, name='export_performance_report'),
]