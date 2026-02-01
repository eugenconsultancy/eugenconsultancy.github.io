"""
Views for orders app.
"""
from .order_views import (
    OrderCreateView, OrderListView, OrderDetailView,
    OrderUpdateView, OrderDeleteView, OrderPaymentView
)
from .writer_views import (
    AvailableOrdersView, WriterOrderListView,
    OrderAssignmentView, OrderDeliveryView
)
from .admin_views import (
    AdminOrderListView, AdminOrderDetailView,
    OrderAssignmentAdminView, OrderDisputeView
)

# Import action views
from .action_views import (
    RevisionRequestView, OrderCompletionView,
    DisputeRaiseView, StartWorkView, AcceptRevisionView,
    WorkSubmissionView, FileUploadView, AdminAssignView,
    AdminCancelView, ForceCompleteView, AdminRefundView,
    AdminReassignView
)

# Import search and API views
from .search_views import (
    OrderSearchView, OrderFilterView, ExportOrdersView
)
from .api_views import (
    OrderStatusAPIView, TimeRemainingAPIView,
    AvailableWritersAPIView
)

__all__ = [
    # Client views
    'OrderCreateView', 'OrderListView', 'OrderDetailView',
    'OrderUpdateView', 'OrderDeleteView', 'OrderPaymentView',
    
    # Writer views
    'AvailableOrdersView', 'WriterOrderListView',
    'OrderAssignmentView', 'OrderDeliveryView',
    
    # Admin views
    'AdminOrderListView', 'AdminOrderDetailView',
    'OrderAssignmentAdminView', 'OrderDisputeView',
    
    # Action views
    'RevisionRequestView', 'OrderCompletionView', 'DisputeRaiseView',
    'StartWorkView', 'AcceptRevisionView', 'WorkSubmissionView',
    'FileUploadView', 'AdminAssignView', 'AdminCancelView',
    'ForceCompleteView', 'AdminRefundView', 'AdminReassignView',
    
    # Search & Export
    'OrderSearchView', 'OrderFilterView', 'ExportOrdersView',
    
    # API views
    'OrderStatusAPIView', 'TimeRemainingAPIView', 'AvailableWritersAPIView',
]