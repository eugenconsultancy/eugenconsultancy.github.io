# apps/documents/views.py
import logging
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from apps.documents.models import (
    GeneratedDocument,
    DocumentTemplate,
    DocumentSignature,
    DocumentAccessLog
)
from apps.documents.services import (
    PDFGenerationService,
    DocumentSecurityService,
    DocumentAccessService
)
from apps.orders.models import Order
from apps.documents.serializers import (
    GeneratedDocumentSerializer,
    DocumentTemplateSerializer,
    DocumentSignatureSerializer,
    SignDocumentSerializer
)

logger = logging.getLogger(__name__)


class GeneratedDocumentListView(generics.ListAPIView):
    """
    List all generated documents for the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GeneratedDocumentSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # Admin can see all documents, users can only see their own
        if user.is_staff:
            queryset = GeneratedDocument.objects.all()
        else:
            queryset = GeneratedDocument.objects.filter(user=user)
        
        # Apply filters
        document_type = self.request.query_params.get('type')
        if document_type:
            queryset = queryset.filter(document_type=document_type)
        
        order_id = self.request.query_params.get('order_id')
        if order_id:
            queryset = queryset.filter(order__order_id__icontains=order_id)
        
        signed_only = self.request.query_params.get('signed')
        if signed_only == 'true':
            queryset = queryset.filter(is_signed=True)
        elif signed_only == 'false':
            queryset = queryset.filter(is_signed=False)
        
        archived = self.request.query_params.get('archived')
        if archived == 'true':
            queryset = queryset.filter(is_archived=True)
        elif archived == 'false':
            queryset = queryset.filter(is_archived=False)
        
        # Date range filter
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(generated_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(generated_at__date__lte=end_date)
        
        return queryset.order_by('-generated_at')


class DocumentDetailView(generics.RetrieveAPIView):
    """
    Retrieve details of a specific document.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GeneratedDocumentSerializer
    
    def get_object(self):
        document_id = self.kwargs.get('document_id')
        document = get_object_or_404(
            GeneratedDocument.objects.select_related(
                'user',
                'order',
                'generated_by',
                'signed_by'
            ),
            id=document_id
        )
        
        # Check authorization
        if not DocumentAccessService.can_user_access_document(document, self.request.user):
            self.permission_denied(
                self.request,
                message="You are not authorized to view this document"
            )
        
        # Log access
        DocumentAccessService.log_document_access(
            document=document,
            user=self.request.user,
            access_type='view',
            request=self.request
        )
        
        return document


class DocumentDownloadView(APIView):
    """
    Download a generated document.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, document_id):
        try:
            document = get_object_or_404(GeneratedDocument, id=document_id)
            
            # Check authorization
            if not DocumentAccessService.can_user_access_document(document, request.user):
                return Response(
                    {'error': 'Not authorized to download this document'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Verify document integrity
            if not DocumentSecurityService.verify_document_integrity(document):
                logger.warning(f"Document integrity check failed for {document_id}")
                return Response(
                    {'error': 'Document integrity verification failed'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Log download
            DocumentAccessService.log_document_access(
                document=document,
                user=request.user,
                access_type='download',
                request=request
            )
            
            # Serve file
            response = FileResponse(
                document.file.open('rb'),
                content_type='application/pdf',
                filename=f"{document.title}.pdf"
            )
            
            response['Content-Disposition'] = f'attachment; filename="{document.title}.pdf"'
            
            logger.info(f"Document downloaded: {document.title} by {request.user.email}")
            
            return response
            
        except GeneratedDocument.DoesNotExist:
            return Response(
                {'error': 'Document not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error downloading document {document_id}: {e}")
            return Response(
                {'error': 'Failed to download document'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentSignView(APIView):
    """
    Digitally sign a document.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, document_id):
        try:
            document = get_object_or_404(
                GeneratedDocument.objects.select_related('user'),
                id=document_id
            )
            
            # Check if already signed
            if document.is_signed:
                return Response(
                    {'error': 'Document is already signed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check authorization
            if document.user != request.user and not request.user.is_staff:
                return Response(
                    {'error': 'Not authorized to sign this document'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Generate digital signature
            signature_data = DocumentSecurityService.generate_digital_signature(
                document=document,
                user=request.user
            )
            
            if not signature_data:
                return Response(
                    {'error': 'Failed to generate digital signature'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Sign the document
            document.sign(
                signed_by=request.user,
                signature_data=signature_data
            )
            
            # Create signature record
            signature = DocumentSignature.objects.create(
                document=document,
                signature_data=signature_data,
                signature_hash=signature_data.split('|')[1] if '|' in signature_data else '',
                signed_by=request.user
            )
            
            # Log signing action
            DocumentAccessService.log_document_access(
                document=document,
                user=request.user,
                access_type='sign',
                request=request
            )
            
            logger.info(f"Document signed: {document.title} by {request.user.email}")
            
            return Response(
                {
                    'status': 'Document signed successfully',
                    'signature_id': str(signature.id),
                    'signed_at': document.signed_at
                },
                status=status.HTTP_200_OK
            )
            
        except GeneratedDocument.DoesNotExist:
            return Response(
                {'error': 'Document not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error signing document {document_id}: {e}")
            return Response(
                {'error': 'Failed to sign document'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentVerifyView(APIView):
    """
    Verify a document's digital signature.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, document_id):
        try:
            document = get_object_or_404(GeneratedDocument, id=document_id)
            
            # Check if document is signed
            if not document.is_signed:
                return Response(
                    {'error': 'Document is not signed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check authorization
            if not DocumentAccessService.can_user_access_document(document, request.user):
                return Response(
                    {'error': 'Not authorized to verify this document'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Verify signature
            is_valid = DocumentSecurityService.verify_digital_signature(document)
            
            # Update signature record if admin
            if request.user.is_staff and is_valid:
                try:
                    signature = DocumentSignature.objects.get(document=document)
                    signature.verify(verified_by=request.user)
                    signature.save()
                except DocumentSignature.DoesNotExist:
                    pass
            
            # Log verification
            DocumentAccessService.log_document_access(
                document=document,
                user=request.user,
                access_type='verify',
                request=request
            )
            
            return Response(
                {
                    'is_valid': is_valid,
                    'signed_by': document.signed_by.email if document.signed_by else None,
                    'signed_at': document.signed_at,
                    'integrity_check': DocumentSecurityService.verify_document_integrity(document)
                },
                status=status.HTTP_200_OK
            )
            
        except GeneratedDocument.DoesNotExist:
            return Response(
                {'error': 'Document not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error verifying document {document_id}: {e}")
            return Response(
                {'error': 'Failed to verify document'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GenerateInvoiceView(APIView):
    """
    Generate an invoice for an order.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, order_id):
        try:
            order = get_object_or_404(Order, order_id=order_id)
            
            # Check authorization
            if (order.client != request.user and 
                order.assigned_writer != request.user and
                not request.user.is_staff):
                return Response(
                    {'error': 'Not authorized to generate invoice for this order'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if invoice already exists
            existing_invoice = GeneratedDocument.objects.filter(
                order=order,
                document_type='invoice'
            ).first()
            
            if existing_invoice:
                return Response(
                    {
                        'status': 'Invoice already exists',
                        'document_id': str(existing_invoice.id),
                        'download_url': f'/documents/{existing_invoice.id}/download/'
                    },
                    status=status.HTTP_200_OK
                )
            
            # Generate invoice
            invoice = PDFGenerationService.generate_invoice(
                order=order,
                user=request.user
            )
            
            if not invoice:
                return Response(
                    {'error': 'Failed to generate invoice'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            logger.info(f"Invoice generated for order {order_id} by {request.user.email}")
            
            return Response(
                {
                    'status': 'Invoice generated successfully',
                    'document_id': str(invoice.id),
                    'title': invoice.title,
                    'download_url': f'/documents/{invoice.id}/download/'
                },
                status=status.HTTP_201_CREATED
            )
            
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error generating invoice for order {order_id}: {e}")
            return Response(
                {'error': 'Failed to generate invoice'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GenerateOrderSummaryView(APIView):
    """
    Generate an order summary document.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, order_id):
        try:
            order = get_object_or_404(Order, order_id=order_id)
            
            # Check authorization
            if (order.client != request.user and 
                order.assigned_writer != request.user and
                not request.user.is_staff):
                return Response(
                    {'error': 'Not authorized to generate summary for this order'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Generate order summary
            summary = PDFGenerationService.generate_order_summary(
                order=order,
                user=request.user
            )
            
            if not summary:
                return Response(
                    {'error': 'Failed to generate order summary'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            logger.info(f"Order summary generated for order {order_id} by {request.user.email}")
            
            return Response(
                {
                    'status': 'Order summary generated successfully',
                    'document_id': str(summary.id),
                    'title': summary.title,
                    'download_url': f'/documents/{summary.id}/download/'
                },
                status=status.HTTP_201_CREATED
            )
            
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error generating order summary for order {order_id}: {e}")
            return Response(
                {'error': 'Failed to generate order summary'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ArchiveDocumentView(APIView):
    """
    Archive a document (admin only).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def post(self, request, document_id):
        try:
            document = get_object_or_404(GeneratedDocument, id=document_id)
            
            # Check if already archived
            if document.is_archived:
                return Response(
                    {'error': 'Document is already archived'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Archive document
            document.archive(archived_by=request.user)
            
            logger.info(f"Document archived: {document.title} by {request.user.email}")
            
            return Response(
                {'status': 'Document archived successfully'},
                status=status.HTTP_200_OK
            )
            
        except GeneratedDocument.DoesNotExist:
            return Response(
                {'error': 'Document not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error archiving document {document_id}: {e}")
            return Response(
                {'error': 'Failed to archive document'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TemplateListView(generics.ListAPIView):
    """
    List all document templates (admin only).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = DocumentTemplateSerializer
    
    def get_queryset(self):
        queryset = DocumentTemplate.objects.all().order_by('name')
        
        # Apply filters
        template_type = self.request.query_params.get('type')
        if template_type:
            queryset = queryset.filter(template_type=template_type)
        
        is_active = self.request.query_params.get('active')
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)
        
        return queryset


class TemplateCreateView(generics.CreateAPIView):
    """
    Create a new document template (admin only).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = DocumentTemplateSerializer
    parser_classes = [MultiPartParser, FormParser]
    
    def perform_create(self, serializer):
        # Set created_by to current user
        serializer.save(created_by=self.request.user)
        
        logger.info(f"Document template created: {serializer.instance.name} by {self.request.user.email}")


class TemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a document template (admin only).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = DocumentTemplateSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        return DocumentTemplate.objects.all()
    
    def perform_update(self, serializer):
        # Increment version on update
        instance = serializer.instance
        instance.version += 1
        serializer.save()
        
        logger.info(f"Document template updated: {instance.name} v{instance.version} by {self.request.user.email}")


class GenerateFromTemplateView(APIView):
    """
    Generate a document from a template (admin only).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def post(self, request):
        try:
            template_name = request.data.get('template_name')
            user_id = request.data.get('user_id')
            order_id = request.data.get('order_id')
            context = request.data.get('context', {})
            document_type = request.data.get('document_type', 'report')
            title = request.data.get('title')
            
            if not template_name or not user_id:
                return Response(
                    {'error': 'template_name and user_id are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get user
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            user = get_object_or_404(User, id=user_id)
            
            # Get order if provided
            order = None
            if order_id:
                order = get_object_or_404(Order, order_id=order_id)
            
            # Generate document
            document = PDFGenerationService.generate_from_template(
                template_name=template_name,
                context=context,
                user=user,
                document_type=document_type,
                title=title,
                order=order
            )
            
            if not document:
                return Response(
                    {'error': 'Failed to generate document from template'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            logger.info(f"Document generated from template {template_name} for user {user.email}")
            
            return Response(
                {
                    'status': 'Document generated successfully',
                    'document_id': str(document.id),
                    'title': document.title,
                    'download_url': f'/documents/{document.id}/download/'
                },
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Error generating document from template: {e}")
            return Response(
                {'error': 'Failed to generate document from template'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentAccessLogsView(APIView):
    """
    Get access logs for a document (admin only).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def get(self, request, document_id):
        try:
            document = get_object_or_404(GeneratedDocument, id=document_id)
            
            # Get query parameters
            days = int(request.query_params.get('days', 30))
            access_type = request.query_params.get('access_type')
            
            # Get access logs
            logs = DocumentAccessService.get_document_access_logs(
                document=document,
                days=days,
                access_type=access_type
            )
            
            # Serialize logs
            serialized_logs = []
            for log in logs:
                serialized_logs.append({
                    'id': str(log.id),
                    'user_email': log.user.email,
                    'access_type': log.access_type,
                    'access_type_display': log.get_access_type_display(),
                    'ip_address': log.ip_address,
                    'user_agent': log.user_agent,
                    'was_successful': log.was_successful,
                    'error_message': log.error_message,
                    'accessed_at': log.accessed_at
                })
            
            return Response(
                {
                    'document_id': str(document.id),
                    'document_title': document.title,
                    'access_logs': serialized_logs,
                    'total_logs': len(serialized_logs)
                },
                status=status.HTTP_200_OK
            )
            
        except GeneratedDocument.DoesNotExist:
            return Response(
                {'error': 'Document not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error getting access logs for document {document_id}: {e}")
            return Response(
                {'error': 'Failed to get access logs'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )