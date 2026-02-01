"""
Serializers for revision management.
"""
from rest_framework import serializers
from django.utils import timezone

from .models import RevisionRequest, RevisionCycle, RevisionAuditLog
from apps.orders.models import Order
from apps.accounts.models import User


class RevisionAuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for revision audit logs.
    """
    performed_by_email = serializers.EmailField(source='performed_by.email', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = RevisionAuditLog
        fields = [
            'id', 'action', 'action_display', 'details',
            'performed_by', 'performed_by_email', 'performed_at',
            'ip_address', 'user_agent'
        ]
        read_only_fields = fields


class RevisionRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for revision requests.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    client_email = serializers.EmailField(source='client.email', read_only=True)
    writer_email = serializers.EmailField(source='writer.email', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    revisions_remaining = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = RevisionRequest
        fields = [
            'id', 'order', 'order_number', 'title', 'instructions',
            'client', 'client_email', 'writer', 'writer_email',
            'status', 'status_display', 'deadline', 'is_overdue',
            'max_revisions_allowed', 'revisions_used', 'revisions_remaining',
            'requested_at', 'started_at', 'completed_at',
            'original_files', 'revised_files', 'created_by', 'last_modified'
        ]
        read_only_fields = [
            'id', 'client', 'writer', 'status', 'requested_at',
            'started_at', 'completed_at', 'created_by', 'last_modified',
            'is_overdue', 'revisions_remaining'
        ]
    
    def validate_deadline(self, value):
        """
        Validate deadline is in the future.
        """
        if value <= timezone.now():
            raise serializers.ValidationError("Deadline must be in the future")
        return value
    
    def validate(self, data):
        """
        Validate revision request data.
        """
        order = data.get('order') or self.instance.order if self.instance else None
        
        if order and order.status not in ['delivered', 'in_revision']:
            raise serializers.ValidationError(
                f"Revisions can only be requested for orders in 'delivered' or 'in_revision' status. Current status: {order.status}"
            )
        
        return data


class CreateRevisionRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for creating revision requests.
    """
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    
    class Meta:
        model = RevisionRequest
        fields = ['order', 'title', 'instructions', 'deadline']
    
    def validate(self, data):
        """
        Validate creation of revision request.
        """
        order = data['order']
        
        # Check if user is the client
        if self.context['request'].user != order.client:
            raise serializers.ValidationError("Only the client can request revisions")
        
        # Check if order can have revisions
        if order.status not in ['delivered', 'in_revision']:
            raise serializers.ValidationError(
                f"Cannot request revision for order in status: {order.status}"
            )
        
        # Check revision cycle
        try:
            revision_cycle = order.revision_cycle
            if not revision_cycle.can_request_revision():
                raise serializers.ValidationError(
                    "Revision limit reached or revision period has expired"
                )
        except RevisionCycle.DoesNotExist:
            # New cycle will be created
            pass
        
        return data


class RevisionCycleSerializer(serializers.ModelSerializer):
    """
    Serializer for revision cycles.
    """
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    revisions_remaining = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = RevisionCycle
        fields = [
            'id', 'order', 'order_number',
            'max_revisions_allowed', 'revisions_used', 'revisions_remaining',
            'revision_period_days', 'started_at', 'ends_at',
            'is_active', 'is_expired'
        ]
        read_only_fields = fields