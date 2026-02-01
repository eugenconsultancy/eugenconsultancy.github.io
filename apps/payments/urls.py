from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment processing
    path('process/<int:order_id>/', views.ProcessPaymentView.as_view(), name='process'),
    path('success/<uuid:payment_id>/', views.PaymentSuccessView.as_view(), name='success'),
    path('cancel/<uuid:payment_id>/', views.PaymentCancelView.as_view(), name='cancel'),
    path('webhook/stripe/', views.StripeWebhookView.as_view(), name='stripe_webhook'),
    
    # Payment management
    path('history/', views.PaymentHistoryView.as_view(), name='history'),
    path('detail/<uuid:payment_id>/', views.PaymentDetailView.as_view(), name='detail'),
    path('receipt/<uuid:payment_id>/', views.PaymentReceiptView.as_view(), name='receipt'),
    
    # Refund requests
    path('refund/request/<int:order_id>/', views.RefundRequestView.as_view(), name='request_refund'),
    path('refund/history/', views.RefundHistoryView.as_view(), name='refund_history'),
    
    # Admin payment management
    path('admin/escrow/', views.EscrowManagementView.as_view(), name='admin_escrow'),
    path('admin/release/<uuid:payment_id>/', views.ReleaseEscrowView.as_view(), name='release_escrow'),
    path('admin/refund/<uuid:payment_id>/', views.AdminRefundView.as_view(), name='admin_refund'),
    
    # Wallet (for writers)
    path('wallet/', views.WalletView.as_view(), name='wallet'),
    path('wallet/withdraw/', views.WithdrawFundsView.as_view(), name='withdraw'),
    path('wallet/transactions/', views.TransactionHistoryView.as_view(), name='transactions'),
]