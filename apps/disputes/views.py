"""
Views for dispute resolution.
"""
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
# apps/disputes/views.py

from django.db import models
from django.core.exceptions import ValidationError, PermissionDenied

from .models import Dispute, DisputeEvidence, DisputeMessage
from .serializers import (
    DisputeSerializer,
    DisputeEvidenceSerializer,
    DisputeMessageSerializer,
    CreateDisputeSerializer,
    SubmitEvidenceSerializer
)
from .services import DisputeService
from apps.api.permissions import (
    IsAdminUser,
    DisputeAccessPermission,
    IsOrderPartyOrAdmin
)
from apps.orders.models import Order


class DisputeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing disputes.
    """
    queryset = Dispute.objects.all().select_related(
        'order', 'opened_by', 'against_user', 'assigned_to', 'resolution_proposed_by'
    )
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'reason', 'priority', 'assigned_to']
    search_fields = [
        'order__order_number',
        'title',
        'description',
        'opened_by__email',
        'against_user__email'
    ]
    ordering_fields = ['opened_at', 'sla_deadline', 'priority']
    ordering = ['-opened_at']
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions.
        """
        if self.action == 'create':
            return CreateDisputeSerializer
        return DisputeSerializer
    
    def get_permissions(self):
        """
        Set permissions based on action.
        """
        if self.action in ['create', 'submit_evidence', 'accept_resolution']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['assign', 'propose_resolution', 'escalate']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [DisputeAccessPermission | IsAdminUser]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        if user.is_staff:
            return self.queryset
        
        # Non-admin users can only see disputes they're involved in
        return self.queryset.filter(
            models.Q(opened_by=user) | models.Q(against_user=user)
        )
    
    def perform_create(self, serializer):
        """
        Create dispute via service layer.
        """
        data = serializer.validated_data
        
        dispute = DisputeService.open_dispute(
            order_id=data['order'].id,
            opened_by_id=self.request.user.id,
            data={
                'reason': data['reason'],
                'title': data.get('title', 'Dispute'),
                'description': data['description'],
                'requested_refund_amount': data.get('requested_refund_amount'),
                'priority': data.get('priority', 'medium')
            },
            files=self.request.FILES,
            request=self.request
        )
        
        # Return the created dispute
        serializer.instance = dispute
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def assign(self, request, pk=None):
        """
        Assign dispute to admin.
        """
        dispute = self.get_object()
        
        assigned_to_id = request.data.get('assigned_to')
        if not assigned_to_id:
            return Response(
                {'error': 'assigned_to is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            updated_dispute = DisputeService.assign_dispute(
                dispute_id=dispute.id,
                assigned_to_id=assigned_to_id,
                request=request
            )
            serializer = self.get_serializer(updated_dispute)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[DisputeAccessPermission])
    def submit_evidence(self, request, pk=None):
        """
        Submit evidence for a dispute.
        """
        dispute = self.get_object()
        
        serializer = SubmitEvidenceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            evidence = DisputeService.submit_evidence(
                dispute_id=dispute.id,
                user_id=request.user.id,
                data=serializer.validated_data,
                files=request.FILES,
                request=request
            )
            
            evidence_serializer = DisputeEvidenceSerializer(evidence)
            return Response(evidence_serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def propose_resolution(self, request, pk=None):
        """
        Propose a resolution for a dispute.
        """
        dispute = self.get_object()
        
        resolution_type = request.data.get('resolution_type')
        resolution_details = request.data.get('resolution_details', '')
        
        if not resolution_type:
            return Response(
                {'error': 'resolution_type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = {
            'resolution_type': resolution_type,
            'resolution_details': resolution_details
        }
        
        if resolution_type in ['full_refund', 'partial_refund']:
            if resolution_type == 'full_refund':
                data['refund_amount'] = dispute.order.amount
            else:
                refund_amount = request.data.get('refund_amount')
                if refund_amount:
                    data['refund_amount'] = refund_amount
        
        try:
            updated_dispute = DisputeService.propose_resolution(
                dispute_id=dispute.id,
                admin_id=request.user.id,
                data=data,
                request=request
            )
            serializer = self.get_serializer(updated_dispute)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[DisputeAccessPermission])
    def accept_resolution(self, request, pk=None):
        """
        Accept a proposed resolution.
        """
        dispute = self.get_object()
        
        try:
            updated_dispute = DisputeService.accept_resolution(
                dispute_id=dispute.id,
                user_id=request.user.id,
                request=request
            )
            serializer = self.get_serializer(updated_dispute)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def escalate(self, request, pk=None):
        """
        Escalate a dispute.
        """
        dispute = self.get_object()
        
        try:
            dispute.escalate()
            dispute.save()
            
            # Log the escalation
            from .models import DisputeResolutionLog
            DisputeResolutionLog.objects.create(
                dispute=dispute,
                action='escalated',
                details={'escalated_by': str(request.user.id)},
                performed_by=request.user,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            serializer = self.get_serializer(dispute)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'], permission_classes=[DisputeAccessPermission | IsAdminUser])
    def evidence(self, request, pk=None):
        """
        Get all evidence for a dispute.
        """
        dispute = self.get_object()
        evidence = dispute.evidences.all().order_by('-submitted_at')
        serializer = DisputeEvidenceSerializer(evidence, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[DisputeAccessPermission | IsAdminUser])
    def messages(self, request, pk=None):
        """
        Get all messages for a dispute.
        """
        dispute = self.get_object()
        
        # Filter messages based on visibility
        messages = dispute.messages.all().order_by('sent_at')
        
        # Filter based on user role
        if not request.user.is_staff:
            messages = messages.filter(
                models.Q(visible_to_client=True) | models.Q(visible_to_writer=True)
            )
        
        serializer = DisputeMessageSerializer(messages, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def summary(self, request):
        """
        Get dispute summary for current user.
        """
        try:
            summary = DisputeService.get_dispute_summary(request.user.id)
            return Response(summary)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class DisputeEvidenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing dispute evidence.
    """
    queryset = DisputeEvidence.objects.all().select_related(
        'dispute', 'submitted_by', 'verified_by', 'file'
    )
    serializer_class = DisputeEvidenceSerializer
    permission_classes = [DisputeAccessPermission | IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['evidence_type', 'is_verified', 'dispute']
    search_fields = ['title', 'description', 'content']
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        if user.is_staff:
            return self.queryset
        
        # Non-admin users can only see evidence for disputes they're involved in
        user_disputes = Dispute.objects.filter(
            models.Q(opened_by=user) | models.Q(against_user=user)
        )
        return self.queryset.filter(dispute__in=user_disputes)
    
    def perform_create(self, serializer):
        """
        Create evidence via service layer.
        """
        dispute_id = self.request.data.get('dispute')
        if not dispute_id:
            raise ValidationError("dispute is required")
        
        try:
            evidence = DisputeService.submit_evidence(
                dispute_id=dispute_id,
                user_id=self.request.user.id,
                data=serializer.validated_data,
                files=self.request.FILES,
                request=self.request
            )
            
            # Return the created evidence
            serializer.instance = evidence
            
        except Exception as e:
            raise ValidationError(str(e))


class DisputeMessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing dispute messages.
    """
    queryset = DisputeMessage.objects.all().select_related(
        'dispute', 'sent_by'
    )
    serializer_class = DisputeMessageSerializer
    permission_classes = [DisputeAccessPermission | IsAdminUser]
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        if user.is_staff:
            return self.queryset
        
        # Non-admin users can only see messages for disputes they're involved in
        user_disputes = Dispute.objects.filter(
            models.Q(opened_by=user) | models.Q(against_user=user)
        )
        
        messages = self.queryset.filter(dispute__in=user_disputes)
        
        # Filter based on visibility
        if user.role == 'client':
            messages = messages.filter(visible_to_client=True)
        elif user.role == 'writer':
            messages = messages.filter(visible_to_writer=True)
        
        return messages
    
    def perform_create(self, serializer):
        """
        Create dispute message.
        """
        dispute_id = self.request.data.get('dispute')
        if not dispute_id:
            raise ValidationError("dispute is required")
        
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            
            # Check user has access to this dispute
            user = self.request.user
            if user not in [dispute.opened_by, dispute.against_user] and not user.is_staff:
                raise PermissionDenied("Access denied to this dispute")
            
            message = serializer.save(
                dispute=dispute,
                sent_by=user
            )
            
            # Mark as read by sender
            message.read_by.add(user)
            
            # Create audit log
            from .models import DisputeResolutionLog
            DisputeResolutionLog.objects.create(
                dispute=dispute,
                action='message_sent',
                details={
                    'message_id': str(message.id),
                    'message_type': message.message_type
                },
                performed_by=user,
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Send notifications
            from apps.notifications.tasks import send_notification
            
            # Notify the other party
            other_party = dispute.against_user if user == dispute.opened_by else dispute.opened_by
            send_notification.delay(
                user_id=other_party.id,
                notification_type='dispute_message',
                title='New Dispute Message',
                message=f"New message in dispute for Order #{dispute.order.order_number}",
                related_object_type='dispute',
                related_object_id=str(dispute.id)
            )
            
            # Notify assigned admin if not the sender
            if dispute.assigned_to and dispute.assigned_to != user:
                send_notification.delay(
                    user_id=dispute.assigned_to.id,
                    notification_type='dispute_message',
                    title='New Dispute Message',
                    message=f"New message in dispute {dispute.id.hex[:8]}",
                    related_object_type='dispute',
                    related_object_id=str(dispute.id)
                )
            
        except Dispute.DoesNotExist:
            raise ValidationError("Dispute not found")