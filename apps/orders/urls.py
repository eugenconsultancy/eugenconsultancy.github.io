from django.urls import path, include
from . import views

app_name = 'orders'

# Client URLs
client_patterns = [
    path('create/', views.OrderCreateView.as_view(), name='create'),
    path('', views.OrderListView.as_view(), name='list'),
    path('<int:pk>/', views.OrderDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.OrderUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.OrderDeleteView.as_view(), name='delete'),
    
    # Order actions
    path('<int:pk>/pay/', views.OrderPaymentView.as_view(), name='pay'),
    path('<int:pk>/request-revision/', views.RevisionRequestView.as_view(), name='request_revision'),
    path('<int:pk>/complete/', views.OrderCompletionView.as_view(), name='complete'),
    path('<int:pk>/dispute/', views.DisputeRaiseView.as_view(), name='dispute'),
    
    # File upload
    path('<int:pk>/upload-file/', views.FileUploadView.as_view(), name='upload_file'),
]

# Writer URLs
writer_patterns = [
    path('available/', views.AvailableOrdersView.as_view(), name='available'),
    path('my-orders/', views.WriterOrderListView.as_view(), name='writer_orders'),
    path('assignment/<int:pk>/', views.OrderAssignmentView.as_view(), name='assignment'),
    path('delivery/<int:pk>/', views.OrderDeliveryView.as_view(), name='delivery'),
    
    # Writer actions
    path('<int:pk>/start-work/', views.StartWorkView.as_view(), name='start_work'),
    path('<int:pk>/accept-revision/', views.AcceptRevisionView.as_view(), name='accept_revision'),
    path('<int:pk>/submit-work/', views.WorkSubmissionView.as_view(), name='submit_work'),
]

# Admin URLs
admin_patterns = [
    path('admin/', views.AdminOrderListView.as_view(), name='admin_list'),
    path('admin/<int:pk>/', views.AdminOrderDetailView.as_view(), name='admin_detail'),
    path('admin/assignment/', views.OrderAssignmentAdminView.as_view(), name='admin_assignment'),
    path('admin/dispute/<int:pk>/', views.OrderDisputeView.as_view(), name='admin_dispute'),
    
    # Admin actions
    path('admin/<int:pk>/assign/', views.AdminAssignView.as_view(), name='admin_assign'),
    path('admin/<int:pk>/cancel/', views.AdminCancelView.as_view(), name='admin_cancel'),
    path('admin/<int:pk>/force-complete/', views.ForceCompleteView.as_view(), name='force_complete'),
    path('admin/<int:pk>/refund/', views.AdminRefundView.as_view(), name='admin_refund'),
    path('admin/<int:pk>/reassign/', views.AdminReassignView.as_view(), name='admin_reassign'),
]

# Search & Filters
search_patterns = [
    path('search/', views.OrderSearchView.as_view(), name='search'),
    path('filter/', views.OrderFilterView.as_view(), name='filter'),
    path('export/', views.ExportOrdersView.as_view(), name='export'),
]

urlpatterns = [
    path('', include(client_patterns)),
    path('writer/', include(writer_patterns)),
    path('admin/', include(admin_patterns)),
    path('', include(search_patterns)),
    
    # API endpoints for AJAX
    path('api/order-status/<int:pk>/', views.OrderStatusAPIView.as_view(), name='api_order_status'),
    path('api/time-remaining/<int:pk>/', views.TimeRemainingAPIView.as_view(), name='api_time_remaining'),
    path('api/available-writers/<int:pk>/', views.AvailableWritersAPIView.as_view(), name='api_available_writers'),
]