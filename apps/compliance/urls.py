from django.urls import path
from . import views

app_name = 'compliance'

urlpatterns = [
    # Data requests (GDPR)
    path('data-request/', views.DataRequestView.as_view(), name='data_request'),
    path('data-request/<uuid:request_id>/', views.DataRequestDetailView.as_view(), name='data_request_detail'),
    path('data-request/<uuid:request_id>/cancel/', views.CancelDataRequestView.as_view(), name='cancel_data_request'),
    
    # Consent management
    path('consent/', views.ConsentManagementView.as_view(), name='consent'),
    path('consent/history/', views.ConsentHistoryView.as_view(), name='consent_history'),
    path('consent/withdraw/', views.WithdrawConsentView.as_view(), name='withdraw_consent'),
    
    # Audit logs
    path('audit-logs/', views.AuditLogView.as_view(), name='audit_logs'),
    path('audit-logs/export/', views.ExportAuditLogsView.as_view(), name='export_audit_logs'),
    
    # Admin compliance tools
    path('admin/requests/', views.AdminDataRequestsView.as_view(), name='admin_requests'),
    path('admin/request/<uuid:request_id>/', views.AdminDataRequestDetailView.as_view(), name='admin_request_detail'),
    path('admin/request/<uuid:request_id>/verify/', views.VerifyDataRequestView.as_view(), name='verify_request'),
    path('admin/request/<uuid:request_id>/process/', views.ProcessDataRequestView.as_view(), name='process_request'),
    path('admin/request/<uuid:request_id>/reject/', views.RejectDataRequestView.as_view(), name='reject_request'),
    
    # Retention rules
    path('admin/retention-rules/', views.RetentionRulesView.as_view(), name='retention_rules'),
    path('admin/retention-rules/<int:rule_id>/', views.RetentionRuleDetailView.as_view(), name='retention_rule_detail'),
    path('admin/retention-rules/<int:rule_id>/execute/', views.ExecuteRetentionRuleView.as_view(), name='execute_rule'),
    
    # Compliance reports
    path('admin/compliance-report/', views.ComplianceReportView.as_view(), name='compliance_report'),
    path('admin/gdpr-report/', views.GDPRReportView.as_view(), name='gdpr_report'),
]