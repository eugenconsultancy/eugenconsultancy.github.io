from django.urls import path
from . import views

urlpatterns = [
    # Admin views
    path('fee-structures/', views.fee_structure_list, name='fee_structure_list'),
    path('fee-structures/create/', views.fee_structure_create, name='fee_structure_create'),
    path('fee-structures/<int:pk>/update/', views.fee_structure_update, name='fee_structure_update'),
    
    path('student-fees/', views.student_fee_list, name='student_fee_list'),
    path('assign-fee/', views.assign_fee_to_student, name='assign_fee_to_student'),
    path('add-charge/', views.add_additional_charge, name='add_additional_charge'),
    path('record-payment/', views.record_payment, name='record_payment'),
    path('payments/', views.payment_list, name='payment_list'),
    
    # Student views
    path('my-finances/', views.student_financial_dashboard, name='student_financial_dashboard'),
    path('make-payment/', views.make_payment, name='make_payment'),
    path('payment-status/<int:payment_id>/', views.payment_status, name='payment_status'),
    path('payment-history/', views.payment_history, name='payment_history'),
    
    # M-Pesa callback
    path('mpesa-callback/', views.mpesa_callback, name='mpesa_callback'),
    
     # New URLs
    path('receipt/<int:payment_id>/', views.generate_receipt, name='generate_receipt'),
    path('download-receipt/<int:payment_id>/', views.download_receipt, name='download_receipt'),
    path('financial-report/', views.financial_report, name='financial_report'),
    
    # Common views
    path('fee-summary/', views.fee_summary, name='fee_summary'),
]