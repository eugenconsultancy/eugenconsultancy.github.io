from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Avg, Q
from django.contrib.auth import get_user_model

from apps.accounts.models import WriterProfile, WriterDocument, WriterVerificationStatus
from apps.orders.models import Order, OrderFile, DeliveryChecklist
from apps.payments.models import Payment, Refund
from apps.compliance.models import DataRequest, ConsentLog, AuditLog, DataRetentionRule


User = get_user_model()


# Custom Admin Site
class EBWritingAdminSite(admin.AdminSite):
    site_header = "EBWriting Administration"
    site_title = "EBWriting Platform"
    index_title = "Dashboard"
    
    def index(self, request, extra_context=None):
        """Custom admin dashboard."""
        extra_context = extra_context or {}
        
        # Get statistics for dashboard
        extra_context.update({
            'writer_stats': self._get_writer_stats(),
            'order_stats': self._get_order_stats(),
            'payment_stats': self._get_payment_stats(),
            'compliance_stats': self._get_compliance_stats(),
            'recent_activity': self._get_recent_activity(),
            'pending_actions': self._get_pending_actions(),
        })
        
        return super().index(request, extra_context)
    
    def _get_writer_stats(self):
        """Get writer-related statistics."""
        total_writers = User.objects.filter(user_type='writer').count()
        
        verification_stats = {}
        for state_code, state_name in WriterVerificationStatus.STATE_CHOICES:
            count = WriterVerificationStatus.objects.filter(state=state_code).count()
            verification_stats[state_code] = {
                'count': count,
                'name': state_name,
            }
        
        return {
            'total_writers': total_writers,
            'verification_stats': verification_stats,
            'pending_verifications': WriterVerificationStatus.objects.filter(
                state='documents_submitted'
            ).count(),
            'active_writers': WriterProfile.objects.filter(status='active').count(),
        }
    
    def _get_order_stats(self):
        """Get order-related statistics."""
        total_orders = Order.objects.count()
        
        state_stats = {}
        for state_code, state_name in Order.STATE_CHOICES:
            count = Order.objects.filter(state=state_code).count()
            state_stats[state_code] = {
                'count': count,
                'name': state_name,
            }
        
        # Recent orders (last 7 days)
        week_ago = timezone.now() - timezone.timedelta(days=7)
        recent_orders = Order.objects.filter(created_at__gte=week_ago).count()
        
        # Overdue orders
        overdue_orders = Order.objects.filter(
            deadline__lt=timezone.now(),
            state__in=['assigned', 'in_progress', 'in_revision']
        ).count()
        
        return {
            'total_orders': total_orders,
            'state_stats': state_stats,
            'recent_orders': recent_orders,
            'overdue_orders': overdue_orders,
            'avg_order_value': Order.objects.aggregate(
                avg=Avg('price')
            )['avg'] or 0,
        }
    
    def _get_payment_stats(self):
        """Get payment-related statistics."""
        # Escrow balance
        escrow_balance = Payment.objects.filter(
            state='held_in_escrow'
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        
        # Monthly revenue
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0)
        monthly_revenue = Payment.objects.filter(
            created_at__gte=month_start,
            state__in=['held_in_escrow', 'released_to_wallet']
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        
        # Pending releases
        pending_releases = Payment.objects.filter(
            state='held_in_escrow',
            escrow_held_until__lte=timezone.now()
        ).count()
        
        return {
            'escrow_balance': escrow_balance,
            'monthly_revenue': monthly_revenue,
            'pending_releases': pending_releases,
            'total_payments': Payment.objects.count(),
            'refund_rate': self._calculate_refund_rate(),
        }
    
    def _get_compliance_stats(self):
        """Get compliance-related statistics."""
        # Pending data requests
        pending_requests = DataRequest.objects.filter(
            status__in=['received', 'verifying', 'processing']
        ).count()
        
        # Overdue requests
        overdue_requests = DataRequest.objects.filter(
            status__in=['received', 'verifying', 'processing'],
            due_date__lt=timezone.now()
        ).count()
        
        # Consent changes (last 30 days)
        month_ago = timezone.now() - timezone.timedelta(days=30)
        consent_changes = ConsentLog.objects.filter(
            created_at__gte=month_ago
        ).count()
        
        return {
            'pending_requests': pending_requests,
            'overdue_requests': overdue_requests,
            'consent_changes': consent_changes,
            'active_rules': DataRetentionRule.objects.filter(is_active=True).count(),
            'audit_logs_today': AuditLog.objects.filter(
                timestamp__date=timezone.now().date()
            ).count(),
        }
    
    def _calculate_refund_rate(self):
        """Calculate refund rate percentage."""
        total_payments = Payment.objects.count()
        refunded_payments = Payment.objects.filter(state='refunded').count()
        
        if total_payments == 0:
            return 0
        
        return (refunded_payments / total_payments) * 100
    
    def _get_recent_activity(self):
        """Get recent system activity."""
        recent_orders = Order.objects.order_by('-created_at')[:5]
        recent_payments = Payment.objects.order_by('-created_at')[:5]
        recent_verifications = WriterVerificationStatus.objects.order_by('-updated_at')[:5]
        
        return {
            'recent_orders': recent_orders,
            'recent_payments': recent_payments,
            'recent_verifications': recent_verifications,
        }
    
    def _get_pending_actions(self):
        """Get pending actions requiring admin attention."""
        return {
            'unassigned_orders': Order.objects.filter(state='paid', writer__isnull=True).count(),
            'pending_verifications': WriterVerificationStatus.objects.filter(
                state='documents_submitted'
            ).count(),
            'pending_refunds': Refund.objects.filter(
                state__in=['requested', 'under_review']
            ).count(),
            'overdue_requests': DataRequest.objects.filter(
                status__in=['received', 'verifying', 'processing'],
                due_date__lt=timezone.now()
            ).count(),
        }


# Create custom admin site instance
admin_site = EBWritingAdminSite(name='ebwriting_admin')


# Custom ModelAdmins
@admin.register(User, site=admin_site)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'user_type', 'is_active', 'date_joined', 'last_login')
    list_filter = ('user_type', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    fieldsets = (
        ('Authentication', {
            'fields': ('email', 'password')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'phone_number')
        }),
        ('Permissions', {
            'fields': ('user_type', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('GDPR Compliance', {
            'fields': ('terms_accepted', 'privacy_policy_accepted', 'marketing_emails', 'data_anonymized'),
            'classes': ('collapse',),
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('last_login', 'date_joined')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(is_superuser=False)


@admin.register(WriterProfile, site=admin_site)
class WriterProfileAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'status', 'education_level', 'years_of_experience', 'average_rating', 'is_available')
    list_filter = ('status', 'education_level', 'is_available', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'specialization')
    readonly_fields = ('total_earnings', 'completed_orders', 'average_rating', 'created_at', 'updated_at')
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Academic Background', {
            'fields': ('education_level', 'institution', 'graduation_year', 'bio')
        }),
        ('Professional Information', {
            'fields': ('years_of_experience', 'hourly_rate', 'specialization')
        }),
        ('Performance', {
            'fields': ('total_earnings', 'completed_orders', 'average_rating')
        }),
        ('Availability', {
            'fields': ('is_available', 'max_orders', 'current_orders')
        }),
        ('Status', {
            'fields': ('status', 'activated_at', 'profile_completed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_activity'),
            'classes': ('collapse',),
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email'


@admin.register(WriterDocument, site=admin_site)
class WriterDocumentAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'document_type', 'status', 'verified_at', 'expires_at')
    list_filter = ('document_type', 'status', 'scanned_for_virus', 'created_at')
    search_fields = ('user__email', 'original_filename', 'review_notes')
    readonly_fields = ('file_hash', 'file_size', 'mime_type', 'original_filename', 'created_at', 'updated_at')
    fieldsets = (
        ('Document Information', {
            'fields': ('user', 'document_type', 'document', 'description')
        }),
        ('Verification Status', {
            'fields': ('status', 'reviewed_by', 'review_notes', 'rejection_reason')
        }),
        ('Security & Metadata', {
            'fields': ('file_hash', 'scanned_for_virus', 'scan_result', 'original_filename', 'file_size', 'mime_type')
        }),
        ('Validity', {
            'fields': ('verified_at', 'expires_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'


@admin.register(WriterVerificationStatus, site=admin_site)
class WriterVerificationStatusAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'state', 'profile_completed_at', 'documents_submitted_at', 'review_completed_at')
    list_filter = ('state', 'created_at')
    search_fields = ('user__email', 'rejection_reason', 'revision_notes')
    readonly_fields = ('state', 'created_at', 'updated_at')
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Verification State', {
            'fields': ('state',)
        }),
        ('Timestamps', {
            'fields': ('profile_completed_at', 'documents_submitted_at', 'review_started_at', 'review_completed_at')
        }),
        ('Decision Details', {
            'fields': ('approved_by', 'rejected_by', 'rejection_reason', 'revision_notes'),
            'classes': ('collapse',),
        }),
        ('System', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'


@admin.register(Order, site=admin_site)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'client_email', 'writer_email', 'state', 'price', 'deadline', 'created_at')
    list_filter = ('state', 'academic_level', 'urgency', 'created_at')
    search_fields = ('order_number', 'title', 'client__email', 'writer__email', 'subject')
    readonly_fields = ('order_number', 'created_at', 'updated_at', 'revision_count')
    fieldsets = (
        ('Basic Information', {
            'fields': ('order_number', 'client', 'writer', 'title', 'description')
        }),
        ('Order Details', {
            'fields': ('subject', 'academic_level', 'pages', 'words', 'sources', 'formatting_style')
        }),
        ('Timeline', {
            'fields': ('urgency', 'deadline', 'created_at')
        }),
        ('Financial', {
            'fields': ('price', 'writer_payment', 'platform_fee')
        }),
        ('State Management', {
            'fields': ('state', 'revision_count', 'max_revisions', 'dispute_reason')
        }),
        ('Timestamps', {
            'fields': ('paid_at', 'assigned_at', 'started_at', 'delivered_at', 'completed_at', 'cancelled_at', 'refunded_at'),
            'classes': ('collapse',),
        }),
        ('Admin', {
            'fields': ('assigned_by', 'admin_notes'),
            'classes': ('collapse',),
        }),
    )
    
    def client_email(self, obj):
        return obj.client.email if obj.client else '-'
    client_email.short_description = 'Client'
    client_email.admin_order_field = 'client__email'
    
    def writer_email(self, obj):
        return obj.writer.email if obj.writer else '-'
    writer_email.short_description = 'Writer'
    writer_email.admin_order_field = 'writer__email'


@admin.register(Payment, site=admin_site)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'user_email', 'order_number', 'amount', 'state', 'created_at')
    list_filter = ('state', 'payment_method', 'fraud_check_passed', 'created_at')
    search_fields = ('reference_number', 'user__email', 'order__order_number', 'gateway_transaction_id')
    readonly_fields = ('payment_id', 'reference_number', 'created_at', 'updated_at')
    fieldsets = (
        ('Identification', {
            'fields': ('payment_id', 'reference_number', 'order', 'user')
        }),
        ('Payment Details', {
            'fields': ('amount', 'currency', 'payment_method', 'state')
        }),
        ('Escrow Management', {
            'fields': ('escrow_held_until', 'platform_fee', 'writer_amount')
        }),
        ('Gateway Response', {
            'fields': ('gateway_response', 'gateway_transaction_id'),
            'classes': ('collapse',),
        }),
        ('Security', {
            'fields': ('fraud_check_passed', 'fraud_check_details', 'ip_address', 'user_agent'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'processed_at', 'held_in_escrow_at', 'released_at', 'refunded_at', 'failed_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def order_number(self, obj):
        return obj.order.order_number if obj.order else '-'
    order_number.short_description = 'Order'
    order_number.admin_order_field = 'order__order_number'


@admin.register(DataRequest, site=admin_site)
class DataRequestAdmin(admin.ModelAdmin):
    list_display = ('request_id_short', 'user_email', 'request_type', 'status', 'received_at', 'due_date', 'is_overdue')
    list_filter = ('request_type', 'status', 'received_at')
    search_fields = ('request_id', 'user__email', 'description')
    readonly_fields = ('request_id', 'received_at', 'due_date', 'updated_at')
    fieldsets = (
        ('Request Information', {
            'fields': ('request_id', 'user', 'request_type', 'description', 'status')
        }),
        ('Verification', {
            'fields': ('verification_method', 'verification_date', 'verified_by')
        }),
        ('Processing', {
            'fields': ('processing_notes', 'data_provided', 'file_path')
        }),
        ('Rejection/Appeal', {
            'fields': ('rejection_reason', 'appeal_notes'),
            'classes': ('collapse',),
        }),
        ('Timeline', {
            'fields': ('received_at', 'due_date', 'completed_at', 'updated_at')
        }),
    )
    
    def request_id_short(self, obj):
        return str(obj.request_id)[:8]
    request_id_short.short_description = 'Request ID'
    request_id_short.admin_order_field = 'request_id'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def is_overdue(self, obj):
        return obj.is_overdue
    is_overdue.boolean = True
    is_overdue.short_description = 'Overdue'


@admin.register(AuditLog, site=admin_site)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user_email', 'action_type', 'model_name', 'object_id')
    list_filter = ('action_type', 'model_name', 'timestamp')
    search_fields = ('user__email', 'model_name', 'object_id', 'request_path')
    readonly_fields = ('log_id', 'timestamp', 'changes', 'before_state', 'after_state')
    fieldsets = (
        ('Basic Information', {
            'fields': ('log_id', 'user', 'action_type', 'model_name', 'object_id')
        }),
        ('Change Details', {
            'fields': ('changes', 'before_state', 'after_state'),
            'classes': ('collapse',),
        }),
        ('Context', {
            'fields': ('ip_address', 'user_agent', 'request_path', 'session_key'),
            'classes': ('collapse',),
        }),
        ('Timestamp', {
            'fields': ('timestamp',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email if obj.user else 'System'
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# Additional admin registrations
admin_site.register(OrderFile)
admin_site.register(DeliveryChecklist)
admin_site.register(Refund)
admin_site.register(ConsentLog)
admin_site.register(DataRetentionRule)

# Custom actions
def approve_selected_verifications(modeladmin, request, queryset):
    from apps.accounts.services.verification_service import VerificationService
    
    for verification in queryset.filter(state='under_admin_review'):
        try:
            VerificationService.approve_writer(
                verification_id=verification.id,
                admin_user=request.user,
                notes='Approved via admin action'
            )
            modeladmin.message_user(request, f'Approved verification for {verification.user.email}')
        except Exception as e:
            modeladmin.message_user(request, f'Failed to approve {verification.user.email}: {str(e)}', level='error')
approve_selected_verifications.short_description = "Approve selected verifications"

def reject_selected_verifications(modeladmin, request, queryset):
    from apps.accounts.services.verification_service import VerificationService
    
    for verification in queryset.filter(state='under_admin_review'):
        try:
            VerificationService.reject_writer(
                verification_id=verification.id,
                admin_user=request.user,
                reason='Rejected via admin action'
            )
            modeladmin.message_user(request, f'Rejected verification for {verification.user.email}')
        except Exception as e:
            modeladmin.message_user(request, f'Failed to reject {verification.user.email}: {str(e)}', level='error')
reject_selected_verifications.short_description = "Reject selected verifications"

def release_escrow_funds(modeladmin, request, queryset):
    from apps.payments.services.escrow_service import EscrowService
    
    for payment in queryset.filter(state='held_in_escrow'):
        try:
            EscrowService.release_escrow_funds(
                payment_id=payment.id,
                admin_user=request.user
            )
            modeladmin.message_user(request, f'Released funds for payment {payment.reference_number}')
        except Exception as e:
            modeladmin.message_user(request, f'Failed to release funds for {payment.reference_number}: {str(e)}', level='error')
release_escrow_funds.short_description = "Release escrow funds"

# Add custom actions to admin classes
WriterVerificationStatusAdmin.actions = [approve_selected_verifications, reject_selected_verifications]
PaymentAdmin.actions = [release_escrow_funds]