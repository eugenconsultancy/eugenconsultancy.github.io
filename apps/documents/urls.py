# apps/documents/urls.py
from django.urls import path
from apps.documents import views

app_name = 'documents'

urlpatterns = [
    # Document endpoints
    path('', views.GeneratedDocumentListView.as_view(), name='document_list'),
    path('<uuid:document_id>/', views.DocumentDetailView.as_view(), name='document_detail'),
    path('<uuid:document_id>/download/', views.DocumentDownloadView.as_view(), name='document_download'),
    path('<uuid:document_id>/sign/', views.DocumentSignView.as_view(), name='document_sign'),
    path('<uuid:document_id>/verify/', views.DocumentVerifyView.as_view(), name='document_verify'),
    path('<uuid:document_id>/archive/', views.ArchiveDocumentView.as_view(), name='archive_document'),
    
    # Generation endpoints
    path('invoices/<uuid:order_id>/generate/', views.GenerateInvoiceView.as_view(), name='generate_invoice'),
    path('summaries/<uuid:order_id>/generate/', views.GenerateOrderSummaryView.as_view(), name='generate_summary'),
    
    # Admin endpoints
    path('admin/templates/', views.TemplateListView.as_view(), name='template_list'),
    path('admin/templates/create/', views.TemplateCreateView.as_view(), name='template_create'),
    path('admin/templates/<uuid:id>/', views.TemplateDetailView.as_view(), name='template_detail'),
    path('admin/templates/generate/', views.GenerateFromTemplateView.as_view(), name='generate_from_template'),
    path('admin/<uuid:document_id>/access-logs/', views.DocumentAccessLogsView.as_view(), name='access_logs'),
]