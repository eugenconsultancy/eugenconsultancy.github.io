from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.admin import SimpleListFilter
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
from .models import (
    Wallet, Transaction, PayoutRequest,
    CommissionRate, WriterBonus
)
import csv
from django.http import HttpResponse


class BalanceRangeFilter(SimpleListFilter):
    """Filter wallets by balance range"""
    title = 'Balance Range'
    parameter_name = 'balance_range'
    
    def lookups(self, request, model_admin):
        return [
            ('0-50', '$0 - $50'),
            ('50-100', '$50 - $100'),
            ('100-500', '$100 - $500'),
            ('500+', '$500+'),
            ('negative', 'Negative Balance'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == '0-50':
            return queryset.filter(balance__range=(0, 50))
        elif self.value() == '50-100':
            return queryset.filter(balance__range=(50, 100))
        elif self.value() == '100-500':
            return queryset.filter(balance__range=(100, 500))
        elif self.value() == '500+':
            return queryset.filter(balance__gte=500)
        elif self.value() == 'negative':
            return queryset.filter(balance__lt=0)
        return queryset


class PayoutStatusFilter(SimpleListFilter):
    """Filter payout requests by status"""
    title = 'Payout Status'
    parameter_name = 'payout_status'
    
    def lookups(self, request, model_admin):
        return [
            ('pending', 'Pending Review'),
            ('approved', 'Approved'),
            ('processing', 'Processing'),
            ('requires_attention', 'Requires Attention'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'pending':
            return queryset.filter(status='pending')
        elif self.value() == 'approved':
            return queryset.filter(status='approved')
        elif self.value() == 'processing':
            return queryset.filter(status='processing')
        elif self.value() == 'requires_attention':
            return queryset.filter(
                Q(status='pending') & Q(created_at__lt=timezone.now() - timezone.timedelta(days=2))
            )
        return queryset


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = [
        'user_email', 'balance_display', 'pending_balance_display',
        'total_earned_display', 'available_for_payout', 'is_active', 'created_at'
    ]
    list_filter = [
        'is_active', BalanceRangeFilter,
        ('created_at', admin.DateFieldListFilter)
    ]
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = [
        'balance', 'pending_balance', 'total_earned', 'total_paid_out',
        'available_for_payout', 'pending_release', 'created_at', 'updated_at'
    ]
    fieldsets = (
        ('Wallet Information', {
            'fields': ('user', 'is_active', 'minimum_payout_threshold', 'default_payment_method')
        }),
        ('Balances', {
            'fields': (
                'balance', 'pending_balance', 'total_earned',
                'total_paid_out', 'available_for_payout', 'pending_release'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['export_wallets_csv', 'deactivate_wallets', 'adjust_minimum_threshold']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    user_email.admin_order_field = 'user__email'
    
    def balance_display(self, obj):
        return format_html('<strong>${:,.2f}</strong>', obj.balance)
    balance_display.short_description = 'Balance'
    
    def pending_balance_display(self, obj):
        return f"${obj.pending_balance:,.2f}"
    pending_balance_display.short_description = 'Pending'
    
    def total_earned_display(self, obj):
        return f"${obj.total_earned:,.2f}"
    total_earned_display.short_description = 'Total Earned'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def export_wallets_csv(self, request, queryset):
        """Export selected wallets to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="wallets_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'User Email', 'Balance', 'Pending Balance', 'Total Earned',
            'Total Paid Out', 'Minimum Payout', 'Active', 'Created Date'
        ])
        
        for wallet in queryset:
            writer.writerow([
                wallet.user.email,
                wallet.balance,
                wallet.pending_balance,
                wallet.total_earned,
                wallet.total_paid_out,
                wallet.minimum_payout_threshold,
                wallet.is_active,
                wallet.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_wallets_csv.short_description = "Export selected wallets to CSV"
    
    def deactivate_wallets(self, request, queryset):
        """Deactivate selected wallets"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} wallets deactivated.')
    deactivate_wallets.short_description = "Deactivate selected wallets"
    
    def adjust_minimum_threshold(self, request, queryset):
        """Adjust minimum payout threshold"""
        # This would typically redirect to a custom admin view
        self.message_user(request, 'Use bulk edit to adjust thresholds.')
    adjust_minimum_threshold.short_description = "Adjust minimum payout threshold"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_id', 'wallet_user', 'transaction_type_display',
        'amount_display', 'status_display', 'reference_info', 'created_at'
    ]
    list_filter = [
        'transaction_type', 'status', 'reference_type',
        ('created_at', admin.DateFieldListFilter)
    ]
    search_fields = [
        'wallet__user__email', 'reference_id', 'description',
        'initiated_by__email'
    ]
    readonly_fields = [
        'id', 'balance_before', 'balance_after', 'get_created_at',
        'completed_at', 'ip_address'
    ]
    fieldsets = (
        ('Transaction Details', {
            'fields': (
                'wallet', 'transaction_type', 'amount', 'status',
                'reference_type', 'reference_id', 'description'
            )
        }),
        ('Metadata', {
            'fields': ('metadata', 'ip_address', 'initiated_by'),
            'classes': ('collapse',)
        }),
        ('Balance Information', {
            'fields': ('balance_before', 'balance_after'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('get_created_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['mark_as_completed', 'mark_as_failed', 'export_transactions_csv']
    
    def transaction_id(self, obj):
        return str(obj.id)[:8]
    transaction_id.short_description = 'ID'
    
    def wallet_user(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.wallet.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.wallet.user.email)
    wallet_user.short_description = 'User'
    wallet_user.admin_order_field = 'wallet__user__email'
    
    def transaction_type_display(self, obj):
        color_map = {
            'credit': 'green',
            'debit': 'orange',
            'refund': 'red',
            'adjustment': 'blue',
        }
        color = color_map.get(obj.transaction_type, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_transaction_type_display()
        )
    transaction_type_display.short_description = 'Type'
    
    def amount_display(self, obj):
        color = 'green' if obj.transaction_type == 'credit' else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">${:,.2f}</span>',
            color, obj.amount
        )
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        color_map = {
            'completed': 'green',
            'pending': 'orange',
            'failed': 'red',
            'cancelled': 'gray',
        }
        color = color_map.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def reference_info(self, obj):
        if obj.reference_type == 'order' and obj.reference_id:
            url = reverse('admin:orders_order_change', args=[obj.reference_id])
            return format_html('<a href="{}">Order #{}</a>', url, str(obj.reference_id)[:8])
        elif obj.reference_type == 'payout' and obj.reference_id:
            url = reverse('admin:wallet_payoutrequest_change', args=[obj.reference_id])
            return format_html('<a href="{}">Payout #{}</a>', url, str(obj.reference_id)[:8])
        return '-'
    reference_info.short_description = 'Reference'
    
    def get_created_at(self, obj):
        """Get created_at as a method for readonly_fields"""
        return obj.created_at
    get_created_at.short_description = 'Created At'
    
    def mark_as_completed(self, request, queryset):
        """Mark selected transactions as completed"""
        for transaction in queryset.filter(status='pending'):
            try:
                transaction.mark_completed()
                transaction.save()
            except Exception as e:
                self.message_user(request, f'Error: {str(e)}', level='error')
        
        self.message_user(request, f'{queryset.count()} transactions marked as completed.')
    mark_as_completed.short_description = "Mark as completed"
    
    def export_transactions_csv(self, request, queryset):
        """Export transactions to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="transactions_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Transaction ID', 'User Email', 'Type', 'Amount', 'Status',
            'Reference Type', 'Reference ID', 'Description', 'Created Date'
        ])
        
        for transaction in queryset:
            writer.writerow([
                str(transaction.id),
                transaction.wallet.user.email,
                transaction.get_transaction_type_display(),
                transaction.amount,
                transaction.get_status_display(),
                transaction.reference_type,
                str(transaction.reference_id) if transaction.reference_id else '',
                transaction.description[:100],
                transaction.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        return response
    export_transactions_csv.short_description = "Export transactions to CSV"


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = [
        'request_id', 'user_email', 'amount_display', 'payout_method_display',
        'status_display', 'is_eligible_display', 'created_at', 'display_actions'
    ]
    list_filter = [PayoutStatusFilter, 'payout_method']
    search_fields = ['wallet__user__email', 'transaction_reference']
    readonly_fields = [
        'id', 'is_eligible', 'get_created_at', 'get_updated_at',
        'processed_at', 'processed_by'
    ]
    fieldsets = (
        ('Payout Details', {
            'fields': (
                'wallet', 'amount', 'payout_method', 'payout_details',
                'status', 'transaction_reference'
            )
        }),
        ('Admin Information', {
            'fields': ('admin_notes', 'rejection_reason', 'processed_by'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('get_created_at', 'get_updated_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['approve_payouts', 'reject_payouts', 'process_payouts', 'export_payouts_csv']
    
    def request_id(self, obj):
        return str(obj.id)[:8]
    request_id.short_description = 'ID'
    
    def user_email(self, obj):
        return obj.wallet.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'wallet__user__email'
    
    def amount_display(self, obj):
        return format_html('<strong>${:,.2f}</strong>', obj.amount)
    amount_display.short_description = 'Amount'
    
    def payout_method_display(self, obj):
        return obj.get_payout_method_display()
    payout_method_display.short_description = 'Method'
    
    def status_display(self, obj):
        color_map = {
            'completed': 'green',
            'processing': 'blue',
            'approved': 'orange',
            'pending': 'gray',
            'rejected': 'red',
            'cancelled': 'darkgray',
        }
        color = color_map.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def is_eligible_display(self, obj):
        if obj.is_eligible:
            return format_html(
                '<span style="color: green;">✓ Eligible</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">✗ Not Eligible</span>'
            )
    is_eligible_display.short_description = 'Eligibility'
    
    def display_actions(self, obj):
        """Admin action buttons"""
        buttons = []
        if obj.status == 'pending':
            buttons.append(
                f'<a href="approve/{obj.id}/" class="button" style="background-color: #4CAF50; color: white; padding: 5px 10px; text-decoration: none;">Approve</a>'
            )
            buttons.append(
                f'<a href="reject/{obj.id}/" class="button" style="background-color: #f44336; color: white; padding: 5px 10px; text-decoration: none;">Reject</a>'
            )
        elif obj.status == 'approved':
            buttons.append(
                f'<a href="process/{obj.id}/" class="button" style="background-color: #2196F3; color: white; padding: 5px 10px; text-decoration: none;">Process</a>'
            )
        return format_html(' '.join(buttons))
    display_actions.short_description = 'Actions'
    
    def get_created_at(self, obj):
        """Get created_at as a method"""
        return obj.created_at
    get_created_at.short_description = 'Created At'
    
    def get_updated_at(self, obj):
        """Get updated_at as a method"""
        return obj.updated_at
    get_updated_at.short_description = 'Updated At'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('wallet__user')
    
    def approve_payouts(self, request, queryset):
        """Approve selected payout requests"""
        from .services import WalletService
        
        approved = 0
        for payout in queryset.filter(status='pending'):
            try:
                if payout.is_eligible:
                    payout.approve(request.user)
                    payout.save()
                    approved += 1
                else:
                    self.message_user(
                        request,
                        f'Payout {payout.id} is not eligible',
                        level='warning'
                    )
            except Exception as e:
                self.message_user(
                    request,
                    f'Error approving payout {payout.id}: {str(e)}',
                    level='error'
                )
        
        self.message_user(request, f'{approved} payout requests approved.')
    approve_payouts.short_description = "Approve selected payouts"
    
    def reject_payouts(self, request, queryset):
        """Reject selected payout requests"""
        for payout in queryset.filter(status='pending'):
            payout.reject('Rejected by admin via bulk action')
            payout.save()
        
        self.message_user(request, f'{queryset.count()} payout requests rejected.')
    reject_payouts.short_description = "Reject selected payouts"


@admin.register(CommissionRate)
class CommissionRateAdmin(admin.ModelAdmin):
    list_display = [
        'writer_level_display', 'commission_percentage_display',
        'bonus_percentage_display', 'minimum_rating', 'minimum_completed_orders',
        'is_active', 'effective_from', 'effective_until'
    ]
    list_filter = ['is_active', 'writer_level']
    search_fields = ['writer_level']
    # FIXED: Added 'commission_percentage_display' to list_display
    # The error was that 'commission_percentage' was in list_editable but not in list_display
    # Now using 'commission_percentage_display' which is in list_display
    list_display_links = ['writer_level_display']
    list_editable = ['is_active']  # Removed 'commission_percentage' from list_editable
    
    def writer_level_display(self, obj):
        return obj.get_writer_level_display()
    writer_level_display.short_description = 'Writer Level'
    
    def commission_percentage_display(self, obj):
        return format_html('<strong>{}%</strong>', obj.commission_percentage)
    commission_percentage_display.short_description = 'Commission %'
    commission_percentage_display.admin_order_field = 'commission_percentage'
    
    def bonus_percentage_display(self, obj):
        if obj.bonus_percentage > 0:
            return format_html(
                '<span style="color: green;">+{}%</span>',
                obj.bonus_percentage
            )
        return '-'
    bonus_percentage_display.short_description = 'Bonus %'


@admin.register(WriterBonus)
class WriterBonusAdmin(admin.ModelAdmin):
    list_display = [
        'bonus_id', 'user_email', 'bonus_type_display', 'amount_display',
        'calculation_period', 'is_paid', 'paid_at', 'created_at'
    ]
    list_filter = ['bonus_type', 'is_paid']
    search_fields = ['wallet__user__email', 'reason']
    readonly_fields = ['get_created_at']  # Changed from field name to method name
    
    def bonus_id(self, obj):
        return str(obj.id)[:8]
    bonus_id.short_description = 'ID'
    
    def user_email(self, obj):
        return obj.wallet.user.email
    user_email.short_description = 'User'
    
    def bonus_type_display(self, obj):
        return obj.get_bonus_type_display()
    bonus_type_display.short_description = 'Type'
    
    def amount_display(self, obj):
        return format_html('<strong>${:,.2f}</strong>', obj.amount)
    amount_display.short_description = 'Amount'
    
    def calculation_period(self, obj):
        return f"{obj.calculation_period_start} to {obj.calculation_period_end}"
    calculation_period.short_description = 'Period'
    
    def get_created_at(self, obj):
        """Get created_at as a method for readonly_fields"""
        return obj.created_at
    get_created_at.short_description = 'Created At'