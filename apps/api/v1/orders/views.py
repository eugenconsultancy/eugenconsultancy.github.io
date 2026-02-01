"""
API views for orders app.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from apps.orders.models import Order, OrderFile
from .serializers import OrderSerializer, OrderFileSerializer, CreateOrderSerializer
from apps.api.permissions import IsOwnerOrAdmin, IsOrderPartyOrAdmin, IsVerifiedWriter
from apps.orders.services.assignment_service import AssignmentService
from apps.orders.services.delivery_service import DeliveryService


class OrderViewSet(viewsets.ModelViewSet):
    """
    API endpoint for orders.
    
    - Clients can create and view their orders
    - Writers can view assigned orders
    - Admin can view and manage all orders
    """
    queryset = Order.objects.all().select_related('client', 'writer')
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'order_type', 'urgency', 'client', 'writer']
    search_fields = ['title', 'description', 'order_number']
    ordering_fields = ['created_at', 'deadline', 'amount']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions.
        """
        if self.action == 'create':
            return CreateOrderSerializer
        return OrderSerializer
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions for this view.
        """
        if self.action == 'create':
            # Only clients can create orders
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            # Only admin or order owner can modify
            permission_classes = [IsOwnerOrAdmin | permissions.IsAdminUser]
        else:
            # List and retrieve require appropriate access
            permission_classes = [IsOrderPartyOrAdmin | permissions.IsAdminUser]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        if user.is_staff:
            return Order.objects.all()
        
        if user.role == 'client':
            return Order.objects.filter(client=user)
        elif user.role == 'writer':
            return Order.objects.filter(writer=user)
        else:
            return Order.objects.none()
    
    def perform_create(self, serializer):
        """
        Create order with client set to current user.
        """
        serializer.save(client=self.request.user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsVerifiedWriter])
    def accept(self, request, pk=None):
        """
        Writer accepts an assigned order.
        """
        order = self.get_object()
        
        if order.writer != request.user:
            return Response(
                {'error': 'Only assigned writer can accept order'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if order.status != 'assigned':
            return Response(
                {'error': f'Order cannot be accepted in status: {order.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            order.status = 'in_progress'
            order.accepted_at = timezone.now()
            order.save()
            
            # Update audit log
            from apps.orders.models import OrderAuditLog
            OrderAuditLog.objects.create(
                order=order,
                action='accepted',
                performed_by=request.user,
                details={'accepted_at': order.accepted_at.isoformat()}
            )
            
            serializer = self.get_serializer(order)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsOrderPartyOrAdmin])
    def deliver(self, request, pk=None):
        """
        Deliver completed order.
        """
        order = self.get_object()
        
        if order.writer != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Only assigned writer can deliver order'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if order.status != 'in_progress':
            return Response(
                {'error': f'Order cannot be delivered in status: {order.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        files = request.FILES.getlist('files')
        if not files:
            return Response(
                {'error': 'Delivery files are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            DeliveryService.deliver_order(
                order_id=order.id,
                writer_id=request.user.id,
                files=files,
                notes=request.data.get('notes', ''),
                request=request
            )
            
            serializer = self.get_serializer(order)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsOrderPartyOrAdmin])
    def complete(self, request, pk=None):
        """
        Client marks order as complete.
        """
        order = self.get_object()
        
        if order.client != request.user:
            return Response(
                {'error': 'Only client can mark order as complete'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if order.status != 'delivered':
            return Response(
                {'error': f'Order cannot be completed in status: {order.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            order.status = 'completed'
            order.completed_at = timezone.now()
            order.save()
            
            # Release escrow payment
            from apps.payments.services.escrow_service import EscrowService
            EscrowService.release_to_writer(order)
            
            serializer = self.get_serializer(order)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'], permission_classes=[IsOrderPartyOrAdmin])
    def timeline(self, request, pk=None):
        """
        Get order timeline with all status changes.
        """
        order = self.get_object()
        
        from apps.orders.models import OrderAuditLog
        timeline = OrderAuditLog.objects.filter(order=order).order_by('performed_at')
        
        timeline_data = []
        for log in timeline:
            timeline_data.append({
                'action': log.action,
                'performed_by': log.performed_by.email if log.performed_by else 'System',
                'performed_at': log.performed_at.isoformat(),
                'details': log.details
            })
        
        return Response(timeline_data)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def stats(self, request):
        """
        Get order statistics for current user.
        """
        user = request.user
        
        if user.is_staff:
            queryset = Order.objects.all()
        elif user.role == 'client':
            queryset = Order.objects.filter(client=user)
        elif user.role == 'writer':
            queryset = Order.objects.filter(writer=user)
        else:
            queryset = Order.objects.none()
        
        stats = {
            'total': queryset.count(),
            'by_status': {},
            'recent_activity': []
        }
        
        # Count by status
        for status_choice in Order.STATUS_CHOICES:
            status_code = status_choice[0]
            count = queryset.filter(status=status_code).count()
            stats['by_status'][status_code] = count
        
        # Recent activity (last 10 orders)
        recent_orders = queryset.order_by('-updated_at')[:10]
        stats['recent_orders'] = OrderSerializer(recent_orders, many=True).data
        
        return Response(stats)


class OrderFileViewSet(viewsets.ModelViewSet):
    """
    API endpoint for order files.
    """
    queryset = OrderFile.objects.all().select_related('order', 'uploaded_by')
    serializer_class = OrderFileSerializer
    permission_classes = [IsOrderPartyOrAdmin | permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['order', 'document_type', 'uploaded_by']
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        if user.is_staff:
            return self.queryset
        
        # Non-admin users can only see files for their orders
        client_orders = Order.objects.filter(client=user)
        writer_orders = Order.objects.filter(writer=user)
        
        return self.queryset.filter(
            order__in=client_orders | writer_orders
        )
    
    def perform_create(self, serializer):
        """
        Create order file with uploader set to current user.
        """
        order = serializer.validated_data['order']
        
        # Check user has access to this order
        user = self.request.user
        if user not in [order.client, order.writer] and not user.is_staff:
            raise PermissionDenied("Access denied to this order")
        
        serializer.save(uploaded_by=user)