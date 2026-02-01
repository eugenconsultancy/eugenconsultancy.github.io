"""
API views for payments app.
"""
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
# apps/api/v1/payments/views.py

from apps.orders.models import Order

from apps.payments.models import Payment, Refund
from .serializers import PaymentSerializer, RefundSerializer
from apps.api.permissions import IsOwnerOrAdmin, IsOrderPartyOrAdmin, IsAdminUser


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for payments.
    Read-only as payments are created by the system.
    """
    queryset = Payment.objects.all().select_related('order', 'user')
    serializer_class = PaymentSerializer
    permission_classes = [IsOrderPartyOrAdmin | IsAdminUser]
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        if user.is_staff:
            return self.queryset
        
        # Non-admin users can only see payments for their orders
        client_orders = Order.objects.filter(client=user)
        writer_orders = Order.objects.filter(writer=user)
        
        return self.queryset.filter(
            order__in=client_orders | writer_orders
        )
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def user_payments(self, request):
        """
        Get payments for current user.
        """
        user = request.user
        
        if user.is_staff:
            payments = Payment.objects.all()
        else:
            payments = Payment.objects.filter(user=user)
        
        serializer = self.get_serializer(payments, many=True)
        return Response(serializer.data)


class RefundViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for refunds.
    Read-only as refunds are created by the system.
    """
    queryset = Refund.objects.all().select_related('payment', 'processed_by')
    serializer_class = RefundSerializer
    permission_classes = [IsOrderPartyOrAdmin | IsAdminUser]
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        if user.is_staff:
            return self.queryset
        
        # Non-admin users can only see refunds for their payments
        user_payments = Payment.objects.filter(user=user)
        
        return self.queryset.filter(
            payment__in=user_payments
        )