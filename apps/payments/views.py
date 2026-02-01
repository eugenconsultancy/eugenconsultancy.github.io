# apps/payments/views.py
import json
import uuid
import stripe
from decimal import Decimal
from django.conf import settings
from django.views.generic import (
    CreateView, ListView, DetailView, TemplateView, 
    FormView, View, UpdateView
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, Sum, Count, Avg  # This defines "Q"
from django.db import models                     # This defines "models"

from apps.orders.models import Order
from apps.payments.models import Payment, Refund
from apps.payments.forms import (
    PaymentForm, RefundRequestForm, WithdrawalForm, 
    AdminRefundForm, EscrowReleaseForm
)
from apps.payments.services.escrow_service import EscrowService
from apps.wallet.models import Wallet, WalletTransaction, PayoutRequest


# ================ PAYMENT PROCESSING VIEWS ================

class ProcessPaymentView(LoginRequiredMixin, CreateView):
    """View for processing new payments."""
    template_name = 'payments/process_payment.html'
    form_class = PaymentForm
    success_url = reverse_lazy('payments:success')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.kwargs.get('order_id')
        order = get_object_or_404(Order, id=order_id, user=self.request.user)
        context['order'] = order
        context['stripe_public_key'] = settings.STRIPE_PUBLIC_KEY
        return context
    
    def form_valid(self, form):
        order_id = self.kwargs.get('order_id')
        order = get_object_or_404(Order, id=order_id, user=self.request.user)
        
        # Check if order already has payment
        if hasattr(order, 'payment'):
            messages.error(self.request, 'This order already has a payment.')
            return redirect('orders:detail', pk=order.id)
        
        # Create payment
        payment = form.save(commit=False)
        payment.order = order
        payment.user = self.request.user
        payment.amount = order.total_price
        payment.ip_address = self.request.META.get('REMOTE_ADDR')
        payment.user_agent = self.request.META.get('HTTP_USER_AGENT', '')
        
        try:
            # Process payment based on method
            if payment.payment_method == 'stripe':
                # Create Stripe payment intent
                stripe.api_key = settings.STRIPE_SECRET_KEY
                
                intent = stripe.PaymentIntent.create(
                    amount=int(payment.amount * 100),  # Convert to cents
                    currency=payment.currency.lower(),
                    payment_method_types=['card'],
                    metadata={
                        'order_id': str(order.id),
                        'user_id': str(self.request.user.id),
                        'payment_id': str(payment.payment_id)
                    },
                    description=f"Order #{order.order_number} - {settings.SITE_NAME}"
                )
                
                payment.gateway_response = intent
                payment.gateway_transaction_id = intent.id
            
            elif payment.payment_method == 'wallet':
                # Check wallet balance
                wallet, created = Wallet.objects.get_or_create(user=self.request.user)
                if wallet.balance < payment.amount:
                    messages.error(self.request, 'Insufficient wallet balance.')
                    return self.form_invalid(form)
                
                # Deduct from wallet
                wallet.balance -= payment.amount
                wallet.save()
                
                # Create wallet transaction
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=payment.amount,
                    transaction_type='payment',
                    description=f"Payment for Order #{order.order_number}",
                    reference=f"PAY-{order.order_number}",
                    status='completed'
                )
            
            payment.save()
            
            # Update order status
            if payment.payment_method != 'wallet':
                payment.start_processing()
                payment.save()
            
            messages.success(self.request, 'Payment initiated successfully.')
            
            if payment.payment_method == 'stripe':
                # Return Stripe client secret for frontend
                return JsonResponse({
                    'client_secret': intent.client_secret,
                    'payment_id': str(payment.payment_id)
                })
            elif payment.payment_method == 'wallet':
                # Process wallet payment immediately
                payment.hold_in_escrow()
                payment.save()
                order.state = 'paid'
                order.save()
                return redirect('payments:success', payment_id=payment.payment_id)
            
        except stripe.error.StripeError as e:
            messages.error(self.request, f'Stripe error: {str(e)}')
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f'Payment error: {str(e)}')
            return self.form_invalid(form)
        
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('payments:success')


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
    """View for successful payment."""
    template_name = 'payments/success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment_id = self.kwargs.get('payment_id')
        payment = get_object_or_404(Payment, payment_id=payment_id, user=self.request.user)
        context['payment'] = payment
        context['order'] = payment.order
        return context


class PaymentCancelView(LoginRequiredMixin, TemplateView):
    """View for cancelled payment."""
    template_name = 'payments/cancel.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment_id = self.kwargs.get('payment_id')
        payment = get_object_or_404(Payment, payment_id=payment_id, user=self.request.user)
        
        # Mark payment as cancelled if still in initiated state
        if payment.state == 'initiated':
            payment.state = 'cancelled'
            payment.save()
        
        context['payment'] = payment
        return context


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    """Handle Stripe webhook events."""
    
    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError as e:
            # Invalid payload
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            return HttpResponse(status=400)
        
        # Handle the event
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            self.handle_payment_success(payment_intent)
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            self.handle_payment_failed(payment_intent)
        
        return HttpResponse(status=200)
    
    def handle_payment_success(self, payment_intent):
        """Handle successful payment."""
        try:
            payment_id = payment_intent['metadata'].get('payment_id')
            payment = Payment.objects.get(payment_id=payment_id)
            
            payment.gateway_response = payment_intent
            payment.fraud_check_passed = True
            payment.hold_in_escrow()
            payment.save()
            
            # Update order
            order = payment.order
            order.state = 'paid'
            order.save()
            
            # Send notification
            # notification_service.send_payment_success(payment)
            
        except Payment.DoesNotExist:
            pass
    
    def handle_payment_failed(self, payment_intent):
        """Handle failed payment."""
        try:
            payment_id = payment_intent['metadata'].get('payment_id')
            payment = Payment.objects.get(payment_id=payment_id)
            
            payment.gateway_response = payment_intent
            payment.mark_as_failed(payment_intent.get('last_payment_error', {}).get('message', ''))
            payment.save()
            
        except Payment.DoesNotExist:
            pass


# ================ PAYMENT MANAGEMENT VIEWS ================

class PaymentHistoryView(LoginRequiredMixin, ListView):
    """View for user's payment history."""
    template_name = 'payments/history.html'
    context_object_name = 'payments'
    paginate_by = 20
    
    def get_queryset(self):
        return Payment.objects.filter(
            user=self.request.user
        ).select_related('order').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add summary statistics
        payments = self.get_queryset()
        context['total_payments'] = payments.count()
        context['total_amount'] = sum(p.amount for p in payments)
        context['active_payments'] = payments.filter(
            state__in=['held_in_escrow', 'processing']
        ).count()
        
        return context


class PaymentDetailView(LoginRequiredMixin, DetailView):
    """View for payment details."""
    template_name = 'payments/detail.html'
    context_object_name = 'payment'
    
    def get_queryset(self):
        return Payment.objects.filter(
            user=self.request.user
        ).select_related('order')
    
    def get_object(self):
        payment_id = self.kwargs.get('payment_id')
        return get_object_or_404(self.get_queryset(), payment_id=payment_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.object
        
        # Add related data
        context['order'] = payment.order
        context['refunds'] = payment.refunds.all()
        
        # Check if user can request refund
        context['can_request_refund'] = self._can_request_refund(payment)
        
        return context
    
    def _can_request_refund(self, payment):
        """Check if user can request refund for this payment."""
        if payment.user != self.request.user:
            return False
        
        valid_states = ['held_in_escrow', 'released_to_wallet']
        if payment.state not in valid_states:
            return False
        
        # Check if order allows refunds
        order = payment.order
        if not order:
            return False
        
        # Check time limits
        max_refund_days = getattr(settings, 'MAX_REFUND_DAYS', 30)
        if (timezone.now() - payment.created_at).days > max_refund_days:
            return False
        
        return True


class PaymentReceiptView(LoginRequiredMixin, DetailView):
    """View for payment receipt (PDF/printable)."""
    template_name = 'payments/receipt.html'
    context_object_name = 'payment'
    
    def get_queryset(self):
        return Payment.objects.filter(
            user=self.request.user
        ).select_related('order')
    
    def get_object(self):
        payment_id = self.kwargs.get('payment_id')
        return get_object_or_404(self.get_queryset(), payment_id=payment_id)
    
    def render_to_response(self, context, **response_kwargs):
        # For PDF generation, you can use:
        # from apps.documents.services.pdf_generator import generate_receipt_pdf
        # return generate_receipt_pdf(context)
        return super().render_to_response(context, **response_kwargs)


# ================ REFUND VIEWS ================

class RefundRequestView(LoginRequiredMixin, CreateView):
    """View for requesting refunds."""
    template_name = 'payments/request_refund.html'
    form_class = RefundRequestForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.kwargs.get('order_id')
        order = get_object_or_404(Order, id=order_id, user=self.request.user)
        context['order'] = order
        
        if hasattr(order, 'payment'):
            context['payment'] = order.payment
        
        return context
    
    def form_valid(self, form):
        order_id = self.kwargs.get('order_id')
        order = get_object_or_404(Order, id=order_id, user=self.request.user)
        
        if not hasattr(order, 'payment'):
            messages.error(self.request, 'No payment found for this order.')
            return redirect('orders:detail', pk=order.id)
        
        payment = order.payment
        
        # Check if refund can be requested
        if not self._can_request_refund(payment):
            messages.error(self.request, 'Refund cannot be requested for this payment.')
            return redirect('payments:detail', payment_id=payment.payment_id)
        
        # Create refund
        refund = form.save(commit=False)
        refund.payment = payment
        refund.order = order
        refund.requested_by = self.request.user
        refund.original_amount = payment.amount
        
        # Set amount based on refund type
        if refund.refund_type == 'full':
            refund.amount = payment.amount
        elif refund.refund_type == 'partial':
            # Partial refund amount should be validated
            if refund.amount > payment.amount:
                form.add_error('amount', 'Refund amount cannot exceed original payment.')
                return self.form_invalid(form)
        
        refund.save()
        
        messages.success(self.request, 'Refund request submitted successfully.')
        
        # Send notification to admin
        # notification_service.send_refund_request_notification(refund)
        
        return redirect('payments:refund_history')
    
    def _can_request_refund(self, payment):
        """Check if refund can be requested."""
        if payment.user != self.request.user:
            return False
        
        valid_states = ['held_in_escrow', 'released_to_wallet']
        if payment.state not in valid_states:
            return False
        
        # Check if already has pending refund
        pending_refunds = payment.refunds.filter(
            state__in=['requested', 'under_review', 'approved', 'processing']
        )
        if pending_refunds.exists():
            return False
        
        return True


class RefundHistoryView(LoginRequiredMixin, ListView):
    """View for user's refund history."""
    template_name = 'payments/refund_history.html'
    context_object_name = 'refunds'
    paginate_by = 20
    
    def get_queryset(self):
        return Refund.objects.filter(
            requested_by=self.request.user
        ).select_related('payment', 'order').order_by('-requested_at')


# ================ ADMIN PAYMENT VIEWS ================

class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to require staff permission."""
    
    def test_func(self):
        return self.request.user.is_staff


class EscrowManagementView(StaffRequiredMixin, ListView):
    """Admin view for managing escrow payments."""
    template_name = 'payments/admin/escrow.html'
    context_object_name = 'payments'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = Payment.objects.filter(
            state='held_in_escrow'
        ).select_related('order', 'user', 'order__writer')
        
        # Filter by search
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(reference_number__icontains=search) |
                Q(order__order_number__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__username__icontains=search)
            )
        
        # Filter by release date
        release_filter = self.request.GET.get('release_filter', '')
        if release_filter == 'ready':
            queryset = queryset.filter(escrow_held_until__lte=timezone.now())
        elif release_filter == 'future':
            queryset = queryset.filter(escrow_held_until__gt=timezone.now())
        
        return queryset.order_by('escrow_held_until')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add summary statistics
        queryset = self.get_queryset()
        context['total_escrow_amount'] = sum(p.amount for p in queryset)
        context['total_writer_amount'] = sum(p.writer_amount for p in queryset)
        context['ready_for_release'] = queryset.filter(
            escrow_held_until__lte=timezone.now()
        ).count()
        
        # Add filter parameters
        context['search'] = self.request.GET.get('search', '')
        context['release_filter'] = self.request.GET.get('release_filter', '')
        
        return context


class ReleaseEscrowView(StaffRequiredMixin, FormView):
    """Admin view for releasing escrow funds."""
    template_name = 'payments/admin/release_escrow.html'
    form_class = EscrowReleaseForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment_id = self.kwargs.get('payment_id')
        payment = get_object_or_404(Payment, payment_id=payment_id)
        context['payment'] = payment
        context['order'] = payment.order
        return context
    
    def form_valid(self, form):
        payment_id = self.kwargs.get('payment_id')
        payment = get_object_or_404(Payment, payment_id=payment_id)
        
        if payment.state != 'held_in_escrow':
            messages.error(self.request, 'Payment is not in escrow.')
            return redirect('payments:admin_escrow')
        
        try:
            with transaction.atomic():
                # Release payment
                payment.release_to_wallet()
                payment.save()
                
                # Update order
                order = payment.order
                order.save()
                
                # Create wallet transaction for writer
                if order.writer:
                    wallet, created = Wallet.objects.get_or_create(user=order.writer)
                    wallet.balance += payment.writer_amount
                    wallet.save()
                    
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=payment.writer_amount,
                        transaction_type='order_payment',
                        description=f"Payment released for Order #{order.order_number}",
                        reference=f"ESCROW-{payment.reference_number}",
                        status='completed'
                    )
                
                messages.success(self.request, 'Escrow funds released successfully.')
                
                # Send notification to writer
                # notification_service.send_escrow_release_notification(payment)
                
        except Exception as e:
            messages.error(self.request, f'Error releasing escrow: {str(e)}')
            return self.form_invalid(form)
        
        return redirect('payments:admin_escrow')


class AdminRefundView(StaffRequiredMixin, UpdateView):
    """Admin view for processing refunds."""
    template_name = 'payments/admin/process_refund.html'
    form_class = AdminRefundForm
    context_object_name = 'refund'
    
    def get_object(self):
        refund_id = self.kwargs.get('refund_id')
        return get_object_or_404(Refund, id=refund_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        refund = self.object
        context['payment'] = refund.payment
        context['order'] = refund.order
        context['user'] = refund.requested_by
        return context
    
    def form_valid(self, form):
        refund = self.object
        action = self.request.POST.get('action')
        
        try:
            with transaction.atomic():
                if action == 'approve':
                    refund.approve(self.request.user, form.cleaned_data.get('review_notes', ''))
                    refund.save()
                    
                    # Start processing if automatic
                    if form.cleaned_data.get('auto_process', False):
                        refund.start_processing()
                        refund.save()
                        
                        # Process refund through payment gateway
                        self._process_refund(refund)
                    
                    messages.success(self.request, 'Refund approved successfully.')
                
                elif action == 'reject':
                    refund.reject(self.request.user, form.cleaned_data.get('rejection_reason', ''))
                    refund.save()
                    messages.success(self.request, 'Refund rejected.')
                
                elif action == 'process':
                    if refund.state != 'approved':
                        messages.error(self.request, 'Refund must be approved before processing.')
                        return self.form_invalid(form)
                    
                    refund.start_processing()
                    refund.save()
                    
                    # Process refund
                    self._process_refund(refund)
                    
                    messages.success(self.request, 'Refund processed successfully.')
        
        except Exception as e:
            messages.error(self.request, f'Error processing refund: {str(e)}')
            return self.form_invalid(form)
        
        return redirect('admin:payments_refund_changelist')
    
    def _process_refund(self, refund):
        """Process refund through payment gateway."""
        payment = refund.payment
        
        if payment.payment_method == 'stripe':
            try:
                stripe.api_key = settings.STRIPE_SECRET_KEY
                
                # Create Stripe refund
                stripe_refund = stripe.Refund.create(
                    payment_intent=payment.gateway_transaction_id,
                    amount=int(refund.amount * 100),  # Convert to cents
                    reason='requested_by_customer' if refund.refund_reason == 'client_request' else 'other'
                )
                
                refund.gateway_response = stripe_refund
                refund.gateway_transaction_id = stripe_refund.id
                refund.complete(stripe_refund)
                refund.save()
                
            except stripe.error.StripeError as e:
                refund.mark_as_failed(str(e))
                refund.save()
                raise
        
        elif payment.payment_method == 'wallet':
            # Refund to wallet
            wallet, created = Wallet.objects.get_or_create(user=payment.user)
            wallet.balance += refund.amount
            wallet.save()
            
            # Create wallet transaction
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=refund.amount,
                transaction_type='refund',
                description=f"Refund for Payment {payment.reference_number}",
                reference=f"REF-{refund.reference_number}",
                status='completed'
            )
            
            refund.complete()
            refund.save()


# ================ WALLET VIEWS ================

class WalletView(LoginRequiredMixin, TemplateView):
    """View for user's wallet dashboard."""
    template_name = 'payments/wallet.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get or create wallet
        wallet, created = Wallet.objects.get_or_create(user=self.request.user)
        context['wallet'] = wallet
        
        # Get recent transactions
        context['recent_transactions'] = WalletTransaction.objects.filter(
            wallet=wallet
        ).order_by('-created_at')[:10]
        
        # Get pending payouts
        context['pending_payouts'] = PayoutRequest.objects.filter(
            wallet=wallet,
            status='pending'
        )
        
        # Get stats
        context['total_earned'] = WalletTransaction.objects.filter(
            wallet=wallet,
            transaction_type='order_payment',
            status='completed'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        context['total_withdrawn'] = WalletTransaction.objects.filter(
            wallet=wallet,
            transaction_type='withdrawal',
            status='completed'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        return context


class WithdrawFundsView(LoginRequiredMixin, CreateView):
    """View for withdrawing funds from wallet."""
    template_name = 'payments/withdraw.html'
    form_class = WithdrawalForm
    success_url = reverse_lazy('payments:wallet')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        wallet = Wallet.objects.get(user=self.request.user)
        amount = form.cleaned_data['amount']
        payment_method = form.cleaned_data['payment_method']
        account_details = form.cleaned_data['account_details']
        
        try:
            with transaction.atomic():
                # Check minimum withdrawal amount
                min_withdrawal = getattr(settings, 'MINIMUM_WITHDRAWAL_AMOUNT', 50.00)
                if amount < min_withdrawal:
                    form.add_error('amount', f'Minimum withdrawal amount is ${min_withdrawal}')
                    return self.form_invalid(form)
                
                # Check wallet balance
                if amount > wallet.balance:
                    form.add_error('amount', 'Insufficient balance')
                    return self.form_invalid(form)
                
                # Check daily limit
                today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
                today_withdrawals = WalletTransaction.objects.filter(
                    wallet=wallet,
                    transaction_type='withdrawal',
                    created_at__gte=today_start,
                    status__in=['pending', 'completed']
                ).aggregate(total=models.Sum('amount'))['total'] or 0
                
                daily_limit = getattr(settings, 'DAILY_WITHDRAWAL_LIMIT', 1000.00)
                if today_withdrawals + amount > daily_limit:
                    form.add_error('amount', f'Daily withdrawal limit exceeded. Limit: ${daily_limit}')
                    return self.form_invalid(form)
                
                # Deduct from wallet
                wallet.balance -= amount
                wallet.save()
                
                # Create withdrawal transaction
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=amount,
                    transaction_type='withdrawal',
                    description=f"Withdrawal request via {payment_method}",
                    reference=f"WDR-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                    status='pending',
                    metadata={
                        'payment_method': payment_method,
                        'account_details': account_details
                    }
                )
                
                # Create payout request
                PayoutRequest.objects.create(
                    wallet=wallet,
                    amount=amount,
                    payment_method=payment_method,
                    account_details=account_details,
                    status='pending'
                )
                
                messages.success(self.request, 'Withdrawal request submitted successfully.')
                
                # Send notification to admin
                # notification_service.send_withdrawal_request_notification(wallet, amount)
        
        except Exception as e:
            messages.error(self.request, f'Error processing withdrawal: {str(e)}')
            return self.form_invalid(form)
        
        return super().form_valid(form)


class TransactionHistoryView(LoginRequiredMixin, ListView):
    """View for wallet transaction history."""
    template_name = 'payments/transactions.html'
    context_object_name = 'transactions'
    paginate_by = 50
    
    def get_queryset(self):
        wallet = Wallet.objects.get(user=self.request.user)
        queryset = WalletTransaction.objects.filter(
            wallet=wallet
        ).order_by('-created_at')
        
        # Filter by type
        transaction_type = self.request.GET.get('type', '')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter parameters
        context['type'] = self.request.GET.get('type', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        
        # Add transaction type choices
        from apps.wallet.models import WalletTransaction
        context['transaction_types'] = WalletTransaction.TRANSACTION_TYPES
        
        return context


# ================ API VIEWS ================

class PaymentStatusAPIView(LoginRequiredMixin, View):
    """API endpoint to check payment status."""
    
    def get(self, request, *args, **kwargs):
        payment_id = request.GET.get('payment_id')
        
        if not payment_id:
            return JsonResponse({'error': 'Payment ID required'}, status=400)
        
        try:
            payment = Payment.objects.get(
                payment_id=payment_id,
                user=request.user
            )
            
            return JsonResponse({
                'status': payment.state,
                'order_id': payment.order.id if payment.order else None,
                'amount': str(payment.amount),
                'currency': payment.currency,
                'created_at': payment.created_at.isoformat(),
            })
        
        except Payment.DoesNotExist:
            return JsonResponse({'error': 'Payment not found'}, status=404)


class WalletBalanceAPIView(LoginRequiredMixin, View):
    """API endpoint to get wallet balance."""
    
    def get(self, request, *args, **kwargs):
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        
        return JsonResponse({
            'balance': str(wallet.balance),
            'currency': wallet.currency,
            'pending_withdrawals': str(PayoutRequest.objects.filter(
                wallet=wallet,
                status='pending'
            ).aggregate(total=models.Sum('amount'))['total'] or 0),
        })


# ================ ERROR VIEWS ================

class PaymentErrorView(TemplateView):
    """View for payment errors."""
    template_name = 'payments/error.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['error_message'] = self.request.GET.get('message', 'An unknown error occurred.')
        return context