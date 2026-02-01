"""
Serializers for dispute resolution.
"""
from rest_framework import serializers
from django.utils import timezone

from .models import Dispute, DisputeEvidence, DisputeMessage
from apps.orders.models import Order
from apps.accounts.models import User


class DisputeSerializer(serializers.ModelSerializer):
    """
    Serializer for disputes.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    resolution_type_display = serializers.CharField(
        source='get_resolution_type_display', 
        read_only=True
    )
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    opened_by_email = serializers.EmailField(source='opened_by.email', read_only=True)
    against_user_email = serializers.EmailField(source='against_user.email', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    sla_status = serializers.CharField(read_only=True)
    
    class Meta:
        model = Dispute
        fields = [
            'id', 'order', 'order_number', 'title', 'description',
            'opened_by', 'opened_by_email', 'against_user', 'against_user_email',
            'reason', 'reason_display', 'status', 'status_display',
            'resolution_type', 'resolution_type_display', 'resolution_details',
            'requested_refund_amount', 'approved_refund_amount',
            'priority', 'priority_display', 'is_overdue', 'sla_status',
            'opened_at', 'under_review_at', 'resolved_at',
            'sla_deadline', 'first_response_at',
            'assigned_to', 'resolution_proposed_by'
        ]
        read_only_fields = [
            'id', 'opened_by', 'against_user', 'status',
            'opened_at', 'under_review_at', 'resolved_at',
            'first_response_at', 'resolution_proposed_by',
            'is_overdue', 'sla_status'
        ]
    
    def validate(self, data):
        """
        Validate dispute data.
        """
        order = data.get('order') or self.instance.order if self.instance else None
        
        if order and self.context['request'].user not in [order.client, order.writer]:
            raise serializers.ValidationError(
                "Only order parties can create disputes"
            )
        
        return data


class CreateDisputeSerializer(serializers.ModelSerializer):
    """
    Serializer for creating disputes.
    """
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    
    class Meta:
        model = Dispute
        fields = [
            'order', 'reason', 'title', 'description',
            'requested_refund_amount', 'priority'
        ]
    
    def validate(self, data):
        """
        Validate dispute creation.
        """
        order = data['order']
        user = self.context['request'].user
        
        # Check if user is a party in the order
        if user not in [order.client, order.writer]:
            raise serializers.ValidationError(
                "Only order parties can create disputes"
            )
        
        # Check if order can be disputed
        if order.status not in ['delivered', 'in_progress', 'completed']:
            raise serializers.ValidationError(
                f"Disputes cannot be opened for orders in status: {order.status}"
            )
        
        # Check for existing active dispute
        existing_dispute = Dispute.objects.filter(
            order=order,
            status__in=['opened', 'under_review', 'awaiting_response', 'evidence_review']
        ).exists()
        
        if existing_dispute:
            raise serializers.ValidationError(
                "An active dispute already exists for this order"
            )
        
        return data


class DisputeEvidenceSerializer(serializers.ModelSerializer):
    """
    Serializer for dispute evidence.
    """
    evidence_type_display = serializers.CharField(source='get_evidence_type_display', read_only=True)
    submitted_by_email = serializers.EmailField(source='submitted_by.email', read_only=True)
    verified_by_email = serializers.EmailField(source='verified_by.email', read_only=True)
    filename = serializers.CharField(source='file.original_filename', read_only=True)
    
    class Meta:
        model = DisputeEvidence
        fields = [
            'id', 'dispute', 'evidence_type', 'evidence_type_display',
            'title', 'description', 'file', 'filename', 'content',
            'submitted_by', 'submitted_by_email', 'submitted_at',
            'admin_notes', 'is_verified', 'verified_by', 'verified_by_email', 'verified_at'
        ]
        read_only_fields = [
            'id', 'submitted_by', 'submitted_at',
            'verified_by', 'verified_at'
        ]
    
    def validate(self, data):
        """
        Validate evidence submission.
        """
        dispute = data.get('dispute') or self.instance.dispute if self.instance else None
        
        if dispute and self.context['request'].user not in [dispute.opened_by, dispute.against_user]:
            raise serializers.ValidationError(
                "Only dispute parties can submit evidence"
            )
        
        # Require either file or content
        if not data.get('file') and not data.get('content'):
            raise serializers.ValidationError(
                "Either file or content must be provided"
            )
        
        return data


class SubmitEvidenceSerializer(serializers.Serializer):
    """
    Serializer for submitting evidence.
    """
    evidence_type = serializers.ChoiceField(choices=DisputeEvidence.EVIDENCE_TYPES)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    content = serializers.CharField(required=False, allow_blank=True)


class DisputeMessageSerializer(serializers.ModelSerializer):
    """
    Serializer for dispute messages.
    """
    message_type_display = serializers.CharField(source='get_message_type_display', read_only=True)
    sent_by_email = serializers.EmailField(source='sent_by.email', read_only=True)
    is_read = serializers.SerializerMethodField()
    
    class Meta:
        model = DisputeMessage
        fields = [
            'id', 'dispute', 'message_type', 'message_type_display',
            'content', 'sent_by', 'sent_by_email', 'sent_at',
            'visible_to_client', 'visible_to_writer', 'visible_to_admin',
            'attachments', 'read_by', 'is_read'
        ]
        read_only_fields = [
            'id', 'sent_by', 'sent_at', 'read_by'
        ]
    
    def get_is_read(self, obj):
        """
        Check if current user has read the message.
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.read_by.filter(id=request.user.id).exists()
        return False
    
    def validate(self, data):
        """
        Validate message creation.
        """
        dispute = data.get('dispute') or self.instance.dispute if self.instance else None
        
        if dispute and self.context['request'].user.is_staff:
            # Admin users can send any type of message
            return data
        
        if dispute and self.context['request'].user not in [dispute.opened_by, dispute.against_user]:
            raise serializers.ValidationError(
                "Only dispute parties can send messages"
            )
        
        return data