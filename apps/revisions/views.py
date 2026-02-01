"""
Views for revision management.
"""
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
# apps/revisions/views.py

from django.core.exceptions import PermissionDenied

from .models import RevisionRequest, RevisionCycle
from .serializers import (
    RevisionRequestSerializer,
    RevisionCycleSerializer,
    RevisionAuditLogSerializer,
    CreateRevisionRequestSerializer
)
from .services import RevisionService
from apps.api.permissions import (
    IsOrderPartyOrAdmin,
    IsOwnerOrAdmin,
    ReadOnlyOrAdmin,
    IsAdminUser
)
from apps.orders.models import Order


class RevisionRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing revision requests.
    """
    queryset = RevisionRequest.objects.all().select_related(
        'order', 'client', 'writer', 'created_by'
    )
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'order', 'client', 'writer']
    search_fields = ['title', 'instructions', 'order__order_number']
    ordering_fields = ['deadline', 'requested_at', 'completed_at']
    ordering = ['-requested_at']
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions.
        """
        if self.action == 'create':
            return CreateRevisionRequestSerializer
        return RevisionRequestSerializer
    
    def get_permissions(self):
        """
        Set permissions based on action.
        """
        if self.action in ['create', 'start', 'complete']:
            permission_classes = [IsOrderPartyOrAdmin]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsOrderPartyOrAdmin | ReadOnlyOrAdmin]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        if user.is_staff:
            return self.queryset
        
        # Non-admin users can only see revisions for their orders
        client_orders = Order.objects.filter(client=user)
        writer_orders = Order.objects.filter(writer=user)
        
        return self.queryset.filter(
            order__in=client_orders | writer_orders
        )
    
    def perform_create(self, serializer):
        """
        Create revision request via service layer.
        """
        data = serializer.validated_data
        order = data['order']
        
        # Validate user is the client for this order
        if self.request.user != order.client and not self.request.user.is_staff:
            raise PermissionDenied("Only the client can request revisions")
        
        revision_request = RevisionService.create_revision_request(
            order_id=order.id,
            client_id=self.request.user.id,
            data={
                'title': data.get('title', f"Revision for Order #{order.order_number}"),
                'instructions': data.get('instructions', ''),
                'deadline': data.get('deadline')
            },
            files=self.request.FILES,
            request=self.request
        )
        
        # Return the created revision
        serializer.instance = revision_request
    
    @action(detail=True, methods=['post'], permission_classes=[IsOrderPartyOrAdmin])
    def start(self, request, pk=None):
        """
        Start working on a revision.
        """
        revision = self.get_object()
        
        # Validate user is the writer for this revision
        if request.user != revision.writer and not request.user.is_staff:
            return Response(
                {'error': 'Only the assigned writer can start revisions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            updated_revision = RevisionService.start_revision(
                revision_id=revision.id,
                writer_id=request.user.id,
                request=request
            )
            serializer = self.get_serializer(updated_revision)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsOrderPartyOrAdmin])
    def complete(self, request, pk=None):
        """
        Complete a revision with files.
        """
        revision = self.get_object()
        
        # Validate user is the writer for this revision
        if request.user != revision.writer and not request.user.is_staff:
            return Response(
                {'error': 'Only the assigned writer can complete revisions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            updated_revision = RevisionService.complete_revision(
                revision_id=revision.id,
                writer_id=request.user.id,
                files=request.FILES,
                request=request
            )
            serializer = self.get_serializer(updated_revision)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'], permission_classes=[IsOrderPartyOrAdmin])
    def order_revisions(self, request):
        """
        Get revisions for a specific order.
        """
        order_id = request.query_params.get('order_id')
        if not order_id:
            return Response(
                {'error': 'order_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            order = Order.objects.get(id=order_id)
            
            # Check user has access to this order
            if request.user not in [order.client, order.writer] and not request.user.is_staff:
                raise PermissionDenied()
            
            revisions = RevisionService.get_revision_history(order.id, request.user.id)
            serializer = self.get_serializer(revisions, many=True)
            return Response(serializer.data)
            
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except PermissionDenied:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )
    
    @action(detail=True, methods=['get'], permission_classes=[IsOrderPartyOrAdmin])
    def audit_logs(self, request, pk=None):
        """
        Get audit logs for a revision.
        """
        revision = self.get_object()
        logs = revision.audit_logs.all().order_by('-performed_at')
        serializer = RevisionAuditLogSerializer(logs, many=True)
        return Response(serializer.data)


class RevisionCycleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing revision cycles.
    Read-only as cycles are managed by the system.
    """
    queryset = RevisionCycle.objects.all().select_related('order')
    serializer_class = RevisionCycleSerializer
    permission_classes = [IsOrderPartyOrAdmin | ReadOnlyOrAdmin]
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        if user.is_staff:
            return self.queryset
        
        # Non-admin users can only see cycles for their orders
        client_orders = Order.objects.filter(client=user)
        writer_orders = Order.objects.filter(writer=user)
        
        return self.queryset.filter(
            order__in=client_orders | writer_orders
        )
    
    @action(detail=True, methods=['get'], permission_classes=[IsOrderPartyOrAdmin])
    def details(self, request, pk=None):
        """
        Get detailed information about a revision cycle.
        """
        revision_cycle = self.get_object()
        
        data = {
            'cycle': RevisionCycleSerializer(revision_cycle).data,
            'revision_requests': RevisionRequestSerializer(
                revision_cycle.revision_requests.all(),
                many=True
            ).data,
            'remaining_revisions': revision_cycle.revisions_remaining,
            'is_expired': revision_cycle.is_expired,
            'days_remaining': (revision_cycle.ends_at - timezone.now()).days
                if not revision_cycle.is_expired else 0
        }
        
        return Response(data)