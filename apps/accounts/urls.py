from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView

from . import views

app_name = 'accounts'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Admin Management
    path('admin/writers/', views.AdminWriterListView.as_view(), name='admin_writers'),
    path('admin/clients/', views.AdminClientListView.as_view(), name='admin_clients'), # Added to fix admin sidebar error
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    # Writer-specific views
    path('writer/profile/', views.WriterProfileView.as_view(), name='writer_profile'),
    path('writer/documents/', views.WriterDocumentsView.as_view(), name='writer_documents'),
    path('writer/verification/', views.VerificationStatusView.as_view(), name='verification_status'),
    path('writer/onboarding/step1/', views.WriterOnboardingStep1View.as_view(), name='writer_onboarding_step1'),
    path('writer/onboarding/step2/', views.WriterOnboardingStep2View.as_view(), name='writer_onboarding_step2'),
    
    # Settings
    path('settings/', views.AccountSettingsView.as_view(), name='settings'),
    path('settings/security/', views.SecuritySettingsView.as_view(), name='security_settings'),
    path('settings/privacy/', views.PrivacySettingsView.as_view(), name='privacy_settings'),
    
    # Password reset (custom)
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='accounts/auth/password_reset.html',
             email_template_name='accounts/emails/password_reset_email.html',
             subject_template_name='accounts/emails/password_reset_subject.txt',
         ), 
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/auth/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/auth/password_reset_confirm.html'
         ), 
         name='password_reset_confirm'),
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/auth/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
    
    # Compliance
    path('data-request/', views.DataRequestView.as_view(), name='data_request'),
    path('consent-history/', views.ConsentHistoryView.as_view(), name='consent_history'),
    
    # API endpoints (for AJAX)
    path('api/update-profile/', views.UpdateProfileAPIView.as_view(), name='api_update_profile'),
    path('api/upload-document/', views.UploadDocumentAPIView.as_view(), name='api_upload_document'),
    path('api/check-username/', views.CheckUsernameView.as_view(), name='api_check_username'),
]