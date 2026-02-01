"""
Serializers for payments app.
"""
from rest_framework import serializers

from apps.payments.models import Payment, Refund


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for payments.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'order_number', 'user', 'user_email',
            'amount', 'payment_method', 'payment_method_display',
            'transaction_id', 'status', 'status_display',
            'created_at', 'completed_at', 'failed_at',
            'failure_reason', 'metadata'
        ]
        read_only_fields = fields


class RefundSerializer(serializers.ModelSerializer):
    """
    Serializer for refunds.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_info = serializers.SerializerMethodField()
    processed_by_email = serializers.EmailField(source='processed_by.email', read_only=True)
    
    class Meta:
        model = Refund
        fields = [
            'id', 'payment', 'payment_info', 'amount',
            'reason', 'status', 'status_display',
            'processed_by', 'processed_by_email',
            'created_at', 'completed_at',
            'transaction_id', 'notes'
        ]
        read_only_fields = fields
    
    def get_payment_info(self, obj):
        """
        Get payment summary.
        """
        return {
            'id': str(obj.payment.id),
            'order_number': obj.payment.order.order_number if obj.payment.order else None,
            'amount': str(obj.payment.amount)
        }