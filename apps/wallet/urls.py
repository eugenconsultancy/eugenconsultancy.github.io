from django.urls import path
from . import views

app_name = 'wallet'

urlpatterns = [
    # Writer wallet views
    path('dashboard/', views.WalletDashboardView.as_view(), name='dashboard'),
    path('request-payout/', views.PayoutRequestCreateView.as_view(), name='request_payout'),
    path('transactions/', views.TransactionHistoryView.as_view(), name='transactions'),
    path('api/summary/', views.wallet_summary_api, name='api_summary'),
    
    # Admin views
    path('admin/payouts/', views.AdminPayoutManagementView.as_view(), name='admin_payouts'),
    path('admin/payouts/<uuid:payout_id>/approve/', views.admin_approve_payout, name='admin_approve_payout'),
    path('admin/payouts/<uuid:payout_id>/process/', views.admin_process_payout, name='admin_process_payout'),
]