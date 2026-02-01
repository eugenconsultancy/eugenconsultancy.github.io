# apps/admin_tools/urls.py
from django.urls import path
from . import views

app_name = 'admin_tools'

urlpatterns = [
    # ===== DASHBOARD =====
    path('dashboard/', views.AdminDashboardView.as_view(), name='dashboard'),
    
    # ===== TASK MANAGEMENT =====
    path('tasks/', views.TaskListView.as_view(), name='tasks'),
    path('tasks/create/', views.TaskCreateView.as_view(), name='task_create'),
    path('tasks/<int:pk>/', views.TaskDetailView.as_view(), name='task_detail'),
    path('tasks/<int:pk>/edit/', views.TaskUpdateView.as_view(), name='task_edit'),
    path('tasks/<int:pk>/delete/', views.TaskDeleteView.as_view(), name='task_delete'),
    path('tasks/<int:pk>/<str:action>/', views.TaskActionView.as_view(), name='task_action'),
    path('tasks/bulk-action/', views.TaskBulkActionView.as_view(), name='task_bulk_action'),
    
    # ===== AUDIT LOGS =====
    path('audit-logs/', views.AuditLogListView.as_view(), name='audit_logs'),
    path('audit-logs/export/', views.AuditLogExportView.as_view(), name='audit_log_export'),
    
    # ===== SYSTEM CONFIGURATION =====
    path('system-config/', views.SystemConfigurationView.as_view(), name='system_config'),
    path('system-config/<int:pk>/update/', views.ConfigurationUpdateView.as_view(), name='config_update'),
    path('system-config/bulk-update/', views.BulkConfigurationUpdateView.as_view(), name='config_bulk_update'),
    
    # ===== SYSTEM HEALTH =====
    path('system-health/', views.SystemHealthView.as_view(), name='system_health'),
    path('system-health/check/', views.SystemHealthCheckView.as_view(), name='system_health_check'),  # Changed from 'health_check'
    path('system-health/<int:pk>/', views.SystemHealthDetailView.as_view(), name='health_check_detail'),
    
    # ===== NOTIFICATION PREFERENCES =====
    path('notification-preferences/', views.NotificationPreferencesView.as_view(), name='notification_preferences'),
    
    # ===== AJAX VIEWS =====
    path('api/task-calendar/', views.TaskCalendarView.as_view(), name='task_calendar'),
    path('api/dashboard-stats/', views.DashboardStatisticsView.as_view(), name='dashboard_stats'),
    path('api/quick-action/', views.AdminQuickActionView.as_view(), name='quick_action'),
    
    # ===== ADDITIONAL VIEWS (from the added view classes) =====
    path('tasks/<int:pk>/assign/', views.TaskAssignView.as_view(), name='task_assign'),
    path('tasks/<int:pk>/complete/', views.TaskCompleteView.as_view(), name='task_complete'),
    path('tasks/<int:pk>/cancel/', views.TaskCancelView.as_view(), name='task_cancel'),
    path('my-tasks/', views.MyTasksView.as_view(), name='my_tasks'),
    path('task-statistics/', views.TaskStatisticsView.as_view(), name='task_statistics'),
    path('writer-review/', views.WriterReviewListView.as_view(), name='writer_review_list'),
    path('writer-review/<int:writer_id>/', views.WriterReviewDetailView.as_view(), name='writer_review_detail'),
    path('order-assignment/', views.OrderAssignmentListView.as_view(), name='order_assignment_list'),
]