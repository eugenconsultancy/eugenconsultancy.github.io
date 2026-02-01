"""
Serializers for orders app.
"""
from rest_framework import serializers
from django.utils import timezone

from apps.orders.models import Order, OrderFile
from apps.accounts.models import User


class OrderFileSerializer(serializers.ModelSerializer):
    """
    Serializer for order files.
    """
    uploaded_by_email = serializers.EmailField(source='uploaded_by.email', read_only=True)
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    
    class Meta:
        model = OrderFile
        fields = [
            'id', 'order', 'document_type', 'document_type_display',
            'original_filename', 'file_size', 'file_url',
            'uploaded_by', 'uploaded_by_email', 'uploaded_at',
            'is_final', 'version'
        ]
        read_only_fields = [
            'id', 'original_filename', 'file_size', 'file_url',
            'uploaded_by', 'uploaded_at', 'version'
        ]
    
    def validate(self, data):
        """
        Validate order file data.
        """
        order = data.get('order') or self.instance.order if self.instance else None
        
        if order and order.status not in ['in_progress', 'delivered', 'in_revision']:
            raise serializers.ValidationError(
                f"Cannot upload files for order in status: {order.status}"
            )
        
        return data


class OrderSerializer(serializers.ModelSerializer):
    """
    Serializer for orders.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    urgency_display = serializers.CharField(source='get_urgency_display', read_only=True)
    client_email = serializers.EmailField(source='client.email', read_only=True)
    writer_email = serializers.EmailField(source='writer.email', read_only=True)
    files = OrderFileSerializer(many=True, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'title', 'description',
            'order_type', 'order_type_display', 'academic_level',
            'pages', 'words', 'urgency', 'urgency_display',
            'deadline', 'amount', 'client', 'client_email',
            'writer', 'writer_email', 'status', 'status_display',
            'is_overdue', 'created_at', 'updated_at',
            'accepted_at', 'delivered_at', 'completed_at',
            'instructions', 'additional_materials',
            'files', 'is_flagged', 'flag_reason'
        ]
        read_only_fields = [
            'id', 'order_number', 'client', 'writer', 'status',
            'created_at', 'updated_at', 'accepted_at',
            'delivered_at', 'completed_at', 'is_overdue',
            'is_flagged', 'flag_reason'
        ]
    
    def validate_deadline(self, value):
        """
        Validate deadline is in the future.
        """
        if value <= timezone.now():
            raise serializers.ValidationError("Deadline must be in the future")
        return value
    
    def validate_amount(self, value):
        """
        Validate amount is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive")
        return value


class CreateOrderSerializer(serializers.ModelSerializer):
    """
    Serializer for creating orders.
    """
    class Meta:
        model = Order
        fields = [
            'title', 'description', 'order_type', 'academic_level',
            'pages', 'words', 'urgency', 'deadline', 'amount',
            'instructions', 'additional_materials'
        ]
    
    def validate(self, data):
        """
        Validate order creation data.
        """
        # Check if user is a client
        if self.context['request'].user.role != 'client':
            raise serializers.ValidationError("Only clients can create orders")
        
        # Validate pages or words
        if not data.get('pages') and not data.get('words'):
            raise serializers.ValidationError("Either pages or words must be specified")
        
        # Calculate amount if not provided
        if not data.get('amount'):
            # Simple calculation based on pages and urgency
            pages = data.get('pages', 1)
            words = data.get('words', 0)
            
            # Convert words to pages if needed (assuming 275 words per page)
            if words > 0:
                pages = max(pages, words / 275)
            
            base_rate = 10.0  # $10 per page
            urgency_multiplier = {
                'standard': 1.0,
                'urgent': 1.5,
                'very_urgent': 2.0
            }
            
            amount = pages * base_rate * urgency_multiplier.get(data.get('urgency', 'standard'), 1.0)
            data['amount'] = round(amount, 2)
        
        return data