"""
Views for plagiarism detection.
"""
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import PlagiarismCheck, PlagiarismReport, PlagiarismPolicy
from .serializers import (
    PlagiarismCheckSerializer,
    PlagiarismReportSerializer,
    PlagiarismPolicySerializer,
    CreatePlagiarismCheckSerializer
)
from .services import PlagiarismService
from apps.api.permissions import (
    IsAdminUser,
    ReadOnlyOrAdmin,
    PlagiarismReportAccessPermission
)
from apps.orders.models import Order


class PlagiarismCheckViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing plagiarism checks.
    Admin-only access for most operations.
    """
    queryset = PlagiarismCheck.objects.all().select_related(
        'order', 'checked_file', 'requested_by', 'processed_by'
    )
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'source', 'similarity_score']
    search_fields = [
        'order__order_number',
        'checked_file__original_filename',
        'raw_result'
    ]
    ordering_fields = ['similarity_score', 'requested_at', 'completed_at']
    ordering = ['-requested_at']
    
    def get_serializer_class(self):
        """
        Use different serializers for different actions.
        """
        if self.action == 'create':
            return CreatePlagiarismCheckSerializer
        return PlagiarismCheckSerializer
    
    def get_permissions(self):
        """
        Set permissions based on action.
        """
        if self.action in ['create', 'retry', 'cancel']:
            permission_classes = [IsAdminUser]
        elif self.action == 'retrieve':
            # Allow retrieval for order parties and admin
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [ReadOnlyOrAdmin]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        if user.is_staff:
            return self.queryset
        
        # Non-admin users can only see checks for their orders
        client_orders = Order.objects.filter(client=user)
        writer_orders = Order.objects.filter(writer=user)
        
        return self.queryset.filter(
            order__in=client_orders | writer_orders
        ).exclude(is_sensitive=True)  # Hide sensitive reports
    
    def perform_create(self, serializer):
        """
        Create plagiarism check via service layer.
        """
        data = serializer.validated_data
        
        plagiarism_check = PlagiarismService.request_plagiarism_check(
            order_id=data['order'].id,
            requested_by_id=self.request.user.id,
            source=data.get('source', 'internal'),
            file_id=data.get('file_to_check'),
            request=self.request
        )
        
        # Return the created check
        serializer.instance = plagiarism_check
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def retry(self, request, pk=None):
        """
        Retry a failed plagiarism check.
        """
        plagiarism_check = self.get_object()
        
        if plagiarism_check.status != 'failed':
            return Response(
                {'error': 'Only failed checks can be retried'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Reset status and retry
            plagiarism_check.status = 'pending'
            plagiarism_check.save()
            
            from .tasks import process_plagiarism_check
            process_plagiarism_check.delay(str(plagiarism_check.id))
            
            serializer = self.get_serializer(plagiarism_check)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def cancel(self, request, pk=None):
        """
        Cancel a pending plagiarism check.
        """
        plagiarism_check = self.get_object()
        
        if plagiarism_check.status not in ['pending', 'processing']:
            return Response(
                {'error': 'Only pending or processing checks can be cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        plagiarism_check.status = 'cancelled'
        plagiarism_check.save()
        
        serializer = self.get_serializer(plagiarism_check)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def summary(self, request, pk=None):
        """
        Get summary of a plagiarism check.
        Non-sensitive summary available to order parties.
        """
        plagiarism_check = self.get_object()
        
        # Check user has access to this order
        order = plagiarism_check.order
        if request.user not in [order.client, order.writer] and not request.user.is_staff:
            return Response(
                {'error': 'Access denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Hide sensitive details for non-admin users
        if plagiarism_check.is_sensitive and not request.user.is_staff:
            return Response({
                'id': str(plagiarism_check.id),
                'status': plagiarism_check.status,
                'risk_level': plagiarism_check.risk_level,
                'is_sensitive': True,
                'message': 'This report contains sensitive information. Contact admin for details.'
            })
        
        serializer = self.get_serializer(plagiarism_check)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def available_sources(self, request):
        """
        Get list of available plagiarism detection sources.
        """
        from .api_clients import PlagiarismClientFactory
        sources = PlagiarismClientFactory.get_available_clients()
        
        source_details = []
        for source in sources:
            source_details.append({
                'name': source,
                'display_name': source.capitalize(),
                'requires_config': source in ['copyscape', 'turnitin']
            })
        
        return Response(source_details)


class PlagiarismReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing plagiarism reports.
    Admin-only access.
    """
    queryset = PlagiarismReport.objects.all().select_related(
        'plagiarism_check',
        'plagiarism_check__order',
        'last_viewed_by'
    )
    serializer_class = PlagiarismReportSerializer
    permission_classes = [PlagiarismReportAccessPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_encrypted', 'expires_at']
    search_fields = ['title', 'summary', 'access_key']
    ordering_fields = ['generated_at', 'view_count', 'expires_at']
    ordering = ['-generated_at']
    
    @action(detail=True, methods=['get'], permission_classes=[PlagiarismReportAccessPermission])
    def details(self, request, pk=None):
        """
        Get detailed report with analysis.
        """
        report = self.get_object()
        
        # Increment view count
        report.increment_view(request.user)
        
        data = {
            'report': PlagiarismReportSerializer(report).data,
            'plagiarism_check': PlagiarismCheckSerializer(report.plagiarism_check).data,
            'order_info': {
                'id': str(report.plagiarism_check.order.id),
                'order_number': report.plagiarism_check.order.order_number,
                'title': report.plagiarism_check.order.title
            }
        }
        
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def by_access_key(self, request):
        """
        Get report by access key (for external sharing).
        """
        access_key = request.query_params.get('access_key')
        
        if not access_key:
            return Response(
                {'error': 'access_key parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            report = PlagiarismService.get_report_by_access_key(access_key, request.user)
            serializer = self.get_serializer(report)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )


class PlagiarismPolicyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing plagiarism policies.
    Admin-only access.
    """
    queryset = PlagiarismPolicy.objects.all()
    serializer_class = PlagiarismPolicySerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering = ['name']
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def evaluate_sample(self, request, pk=None):
        """
        Evaluate a sample similarity score against this policy.
        """
        policy = self.get_object()
        
        similarity_score = request.data.get('similarity_score')
        if similarity_score is None:
            return Response(
                {'error': 'similarity_score is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            similarity_score = float(similarity_score)
            result = policy.evaluate(similarity_score)
            
            return Response({
                'policy': policy.name,
                'similarity_score': similarity_score,
                'evaluation': result,
                'thresholds': {
                    'warning': policy.warning_threshold,
                    'action': policy.action_threshold,
                    'rejection': policy.rejection_threshold
                }
            })
            
        except ValueError:
            return Response(
                {'error': 'Invalid similarity_score format'},
                status=status.HTTP_400_BAD_REQUEST
            )