from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import DetailView, ListView, CreateView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.db import transaction
from decimal import Decimal
import json

from .models import Wallet, PayoutRequest, Transaction, CommissionRate
from .services import WalletService
from ..accounts.decorators import writer_required, admin_required


@method_decorator([login_required, writer_required], name='dispatch')
class WalletDashboardView(DetailView):
    """Writer wallet dashboard"""
    model = Wallet
    template_name = 'wallet/dashboard.html'
    context_object_name = 'wallet'
    
    def get_object(self):
        return WalletService.get_or_create_wallet(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get wallet summary
        summary = WalletService.get_wallet_summary(self.object.id)
        context.update(summary)
        
        # Get recent transactions
        recent_transactions = Transaction.objects.filter(
            wallet=self.object
        ).select_related('wallet__user').order_by('-created_at')[:20]
        context['recent_transactions'] = recent_transactions
        
        # Get pending payout requests
        pending_payouts = PayoutRequest.objects.filter(
            wallet=self.object,
            status__in=['pending', 'approved', 'processing']
        ).order_by('-created_at')
        context['pending_payouts'] = pending_payouts
        
        # Get commission rate
        writer_level = WalletService.calculate_writer_level(self.request.user)
        try:
            commission_rate = CommissionRate.objects.get(
                writer_level=writer_level,
                is_active=True
            )
            context['commission_rate'] = commission_rate
        except CommissionRate.DoesNotExist:
            context['commission_rate'] = None
        
        return context


@method_decorator([login_required, writer_required], name='dispatch')
class PayoutRequestCreateView(CreateView):
    """Create payout request"""
    model = PayoutRequest
    fields = ['amount', 'payout_method', 'payout_details']
    template_name = 'wallet/request_payout.html'
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Customize form fields
        wallet = WalletService.get_or_create_wallet(self.request.user)
        form.fields['amount'].widget.attrs.update({
            'min': wallet.minimum_payout_threshold,
            'max': wallet.balance,
            'step': '0.01'
        })
        return form
    
    def form_valid(self, form):
        try:
            wallet = WalletService.get_or_create_wallet(self.request.user)
            
            with transaction.atomic():
                payout_request = WalletService.request_payout(
                    wallet_id=wallet.id,
                    amount=form.cleaned_data['amount'],
                    payout_method=form.cleaned_data['payout_method'],
                    payout_details=form.cleaned_data.get('payout_details', {})
                )
            
            messages.success(
                self.request,
                f'Payout request for ${payout_request.amount} submitted successfully.'
            )
            return redirect('wallet:dashboard')
            
        except ValidationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f'Error creating payout request: {str(e)}')
            return self.form_invalid(form)
    
    def get_success_url(self):
        return reverse_lazy('wallet:dashboard')


@method_decorator([login_required, writer_required], name='dispatch')
class TransactionHistoryView(ListView):
    """View transaction history"""
    model = Transaction
    template_name = 'wallet/transactions.html'
    paginate_by = 25
    context_object_name = 'transactions'
    
    def get_queryset(self):
        wallet = WalletService.get_or_create_wallet(self.request.user)
        return Transaction.objects.filter(
            wallet=wallet
        ).select_related('wallet__user').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wallet = WalletService.get_or_create_wallet(self.request.user)
        context['wallet'] = wallet
        
        # Add filter parameters
        context['transaction_type'] = self.request.GET.get('type', '')
        context['status'] = self.request.GET.get('status', '')
        
        return context


@login_required
@writer_required
def wallet_summary_api(request):
    """API endpoint for wallet summary (AJAX)"""
    wallet = WalletService.get_or_create_wallet(request.user)
    summary = WalletService.get_wallet_summary(wallet.id)
    
    data = {
        'available_balance': float(summary['available_balance']),
        'pending_balance': float(summary['pending_balance']),
        'total_earned': float(summary['total_earned']),
        'total_paid_out': float(summary['total_paid_out']),
        'recent_earnings_30d': float(summary['recent_earnings_30d']),
        'minimum_threshold': float(summary['minimum_threshold']),
        'eligible_for_payout': summary['eligible_for_payout'],
    }
    
    return JsonResponse(data)


@method_decorator([login_required, admin_required], name='dispatch')
class AdminPayoutManagementView(ListView):
    """Admin view for managing payout requests"""
    model = PayoutRequest
    template_name = 'wallet/admin/payout_management.html'
    paginate_by = 50
    context_object_name = 'payout_requests'
    
    def get_queryset(self):
        queryset = PayoutRequest.objects.filter(
            status__in=['pending', 'approved']
        ).select_related('wallet__user').order_by('-created_at')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Statistics
        context['total_pending'] = PayoutRequest.objects.filter(
            status='pending'
        ).count()
        context['total_approved'] = PayoutRequest.objects.filter(
            status='approved'
        ).count()
        context['total_processing'] = PayoutRequest.objects.filter(
            status='processing'
        ).count()
        
        return context


@login_required
@admin_required
@require_http_methods(['POST'])
def admin_approve_payout(request, payout_id):
    """Admin approve payout request"""
    try:
        payout = get_object_or_404(PayoutRequest, id=payout_id)
        
        if payout.status != 'pending':
            return JsonResponse({
                'success': False,
                'error': 'Payout is not pending approval'
            })
        
        payout.approve(request.user)
        payout.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Payout approved successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@admin_required
@require_http_methods(['POST'])
def admin_process_payout(request, payout_id):
    """Admin process payout (mark as completed)"""
    try:
        from .services import WalletService
        
        payout = get_object_or_404(PayoutRequest, id=payout_id)
        
        if payout.status != 'approved':
            return JsonResponse({
                'success': False,
                'error': 'Payout must be approved before processing'
            })
        
        # Generate reference (in production, this would be from payment gateway)
        reference = f"PYT-{payout.id.hex[:8].upper()}-{timezone.now().strftime('%Y%m%d')}"
        
        WalletService.process_payout(
            payout_request_id=payout.id,
            admin_user=request.user,
            reference=reference
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Payout processed successfully',
            'reference': reference
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })