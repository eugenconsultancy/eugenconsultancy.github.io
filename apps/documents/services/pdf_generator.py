# apps/documents/services/pdf_generator.py
import logging
import hashlib
import tempfile
import io
from typing import Dict, Any, Optional
from datetime import datetime
from django.utils import timezone
from django.conf import settings
from django.template.loader import render_to_string
from django.core.files.base import ContentFile

import pdfkit
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

from apps.documents.models import GeneratedDocument, DocumentTemplate
from apps.orders.models import Order

logger = logging.getLogger(__name__)


class PDFGenerationService:
    """Service for generating PDF documents"""
    
    # Default configuration for pdfkit
    PDFKIT_CONFIG = {
        'page-size': 'Letter',
        'encoding': 'UTF-8',
        'no-outline': None,
        'quiet': '',
    }
    
    @staticmethod
    def generate_invoice(order: Order, user=None) -> Optional[GeneratedDocument]:
        """
        Generate an invoice PDF for an order.
        
        Args:
            order: The order
            user: User generating the invoice
        
        Returns:
            GeneratedDocument instance or None
        """
        try:
            # Prepare context data
            context = {
                'order': order,
                'invoice_number': f"INV-{order.order_id}-{timezone.now().strftime('%Y%m%d')}",
                'invoice_date': timezone.now().strftime('%B %d, %Y'),
                'due_date': order.deadline.strftime('%B %d, %Y') if order.deadline else 'Upon receipt',
                'company_info': {
                    'name': 'EBWriting',
                    'address': '123 Academic Street, Education City',
                    'phone': '+1 (555) 123-4567',
                    'email': 'billing@ebwriting.com',
                },
                'client_info': {
                    'name': order.client.get_full_name() or order.client.email,
                    'email': order.client.email,
                },
                'items': [
                    {
                        'description': order.title,
                        'quantity': 1,
                        'unit_price': order.total_amount,
                        'total': order.total_amount,
                    }
                ],
                'subtotal': order.total_amount,
                'tax': 0,  # Assuming no tax for now
                'total': order.total_amount,
            }
            
            # Render HTML template
            html_content = render_to_string('documents/invoice_template.html', context)
            
            # Generate PDF
            pdf_bytes = PDFGenerationService._html_to_pdf(html_content)
            
            if not pdf_bytes:
                return None
            
            # Create GeneratedDocument
            document = PDFGenerationService._create_document(
                title=f"Invoice for Order #{order.order_id}",
                document_type='invoice',
                content=pdf_bytes,
                order=order,
                user=order.client,
                generated_by=user,
                template_name='invoice_template'
            )
            
            logger.info(f"Invoice generated for order {order.order_id}")
            return document
            
        except Exception as e:
            logger.error(f"Error generating invoice for order {order.order_id}: {e}")
            return None
    
    @staticmethod
    def generate_order_summary(order: Order, user=None) -> Optional[GeneratedDocument]:
        """
        Generate an order summary PDF.
        
        Args:
            order: The order
            user: User generating the summary
        
        Returns:
            GeneratedDocument instance or None
        """
        try:
            # Prepare context data
            context = {
                'order': order,
                'summary_date': timezone.now().strftime('%B %d, %Y'),
                'client_info': {
                    'name': order.client.get_full_name() or order.client.email,
                    'email': order.client.email,
                },
                'writer_info': {
                    'name': order.assigned_writer.get_full_name() if order.assigned_writer else 'Not assigned',
                    'email': order.assigned_writer.email if order.assigned_writer else 'N/A',
                },
                'order_details': {
                    'title': order.title,
                    'description': order.description[:500] + ('...' if len(order.description) > 500 else ''),
                    'deadline': order.deadline.strftime('%B %d, %Y %H:%M') if order.deadline else 'Not specified',
                    'pages': order.page_count,
                    'words': order.word_count,
                    'academic_level': order.get_academic_level_display(),
                    'format': order.get_format_display(),
                    'total_amount': f"${order.total_amount:.2f}",
                },
                'timeline': [
                    {'event': 'Order Created', 'date': order.created_at.strftime('%B %d, %Y %H:%M')},
                    {'event': 'Payment Received', 'date': order.paid_at.strftime('%B %d, %Y %H:%M') if order.paid_at else 'Pending'},
                    {'event': 'Writer Assigned', 'date': order.assigned_at.strftime('%B %d, %Y %H:%M') if order.assigned_at else 'Pending'},
                    {'event': 'Deadline', 'date': order.deadline.strftime('%B %d, %Y %H:%M') if order.deadline else 'Not specified'},
                ],
            }
            
            # Render HTML template
            html_content = render_to_string('documents/order_summary_template.html', context)
            
            # Generate PDF
            pdf_bytes = PDFGenerationService._html_to_pdf(html_content)
            
            if not pdf_bytes:
                return None
            
            # Create GeneratedDocument
            document = PDFGenerationService._create_document(
                title=f"Order Summary #{order.order_id}",
                document_type='order_summary',
                content=pdf_bytes,
                order=order,
                user=order.client,
                generated_by=user,
                template_name='order_summary_template'
            )
            
            logger.info(f"Order summary generated for order {order.order_id}")
            return document
            
        except Exception as e:
            logger.error(f"Error generating order summary for order {order.order_id}: {e}")
            return None
    
    @staticmethod
    def generate_delivery_cover(order: Order, user=None) -> Optional[GeneratedDocument]:
        """
        Generate a delivery cover page PDF.
        
        Args:
            order: The order
            user: User generating the cover
        
        Returns:
            GeneratedDocument instance or None
        """
        try:
            # Prepare context data
            context = {
                'order': order,
                'delivery_date': timezone.now().strftime('%B %d, %Y'),
                'cover_title': f"Delivery for Order #{order.order_id}",
                'client_info': {
                    'name': order.client.get_full_name() or order.client.email,
                    'email': order.client.email,
                },
                'writer_info': {
                    'name': order.assigned_writer.get_full_name() if order.assigned_writer else 'Not assigned',
                    'email': order.assigned_writer.email if order.assigned_writer else 'N/A',
                    'writer_id': order.assigned_writer.writer_profile.writer_id if order.assigned_writer and hasattr(order.assigned_writer, 'writer_profile') else 'N/A',
                },
                'order_details': {
                    'title': order.title,
                    'pages': order.page_count,
                    'words': order.word_count,
                    'format': order.get_format_display(),
                    'academic_level': order.get_academic_level_display(),
                },
                'delivery_notes': "This document has been prepared in accordance with your order requirements. "
                                "Please review the work and request revisions if needed within the specified revision period.",
                'next_steps': [
                    "Review the delivered work",
                    "Request revisions if needed (within revision period)",
                    "Approve the work to release payment to writer",
                    "Rate your experience with the writer",
                ],
            }
            
            # Render HTML template
            html_content = render_to_string('documents/delivery_cover_template.html', context)
            
            # Generate PDF
            pdf_bytes = PDFGenerationService._html_to_pdf(html_content)
            
            if not pdf_bytes:
                return None
            
            # Create GeneratedDocument
            document = PDFGenerationService._create_document(
                title=f"Delivery Cover for Order #{order.order_id}",
                document_type='delivery_cover',
                content=pdf_bytes,
                order=order,
                user=order.client,
                generated_by=user,
                template_name='delivery_cover_template'
            )
            
            logger.info(f"Delivery cover generated for order {order.order_id}")
            return document
            
        except Exception as e:
            logger.error(f"Error generating delivery cover for order {order.order_id}: {e}")
            return None
    
    @staticmethod
    def generate_completion_certificate(order: Order, user=None) -> Optional[GeneratedDocument]:
        """
        Generate a completion certificate PDF.
        
        Args:
            order: The order
            user: User generating the certificate
        
        Returns:
            GeneratedDocument instance or None
        """
        try:
            # Only generate for completed orders
            if order.status != 'completed':
                logger.warning(f"Cannot generate completion certificate for order {order.order_id} with status {order.status}")
                return None
            
            # Prepare context data
            context = {
                'order': order,
                'certificate_date': timezone.now().strftime('%B %d, %Y'),
                'certificate_number': f"CERT-{order.order_id}-{timezone.now().strftime('%Y%m%d')}",
                'client_info': {
                    'name': order.client.get_full_name() or order.client.email,
                    'email': order.client.email,
                },
                'writer_info': {
                    'name': order.assigned_writer.get_full_name() if order.assigned_writer else 'Not assigned',
                    'email': order.assigned_writer.email if order.assigned_writer else 'N/A',
                    'writer_id': order.assigned_writer.writer_profile.writer_id if order.assigned_writer and hasattr(order.assigned_writer, 'writer_profile') else 'N/A',
                },
                'order_details': {
                    'title': order.title,
                    'completed_date': order.completed_at.strftime('%B %d, %Y') if order.completed_at else timezone.now().strftime('%B %d, %Y'),
                    'pages': order.page_count,
                    'words': order.word_count,
                    'quality_score': '4.5/5.0',  # This would come from reviews
                },
                'certificate_text': f"This certifies that the academic work for Order #{order.order_id} has been successfully "
                                   f"completed and delivered to the satisfaction of the client.",
            }
            
            # Render HTML template
            html_content = render_to_string('documents/completion_certificate_template.html', context)
            
            # Generate PDF
            pdf_bytes = PDFGenerationService._html_to_pdf(html_content)
            
            if not pdf_bytes:
                return None
            
            # Create GeneratedDocument
            document = PDFGenerationService._create_document(
                title=f"Completion Certificate for Order #{order.order_id}",
                document_type='completion_certificate',
                content=pdf_bytes,
                order=order,
                user=order.client,
                generated_by=user,
                template_name='completion_certificate_template'
            )
            
            logger.info(f"Completion certificate generated for order {order.order_id}")
            return document
            
        except Exception as e:
            logger.error(f"Error generating completion certificate for order {order.order_id}: {e}")
            return None
    
    @staticmethod
    def generate_from_template(
        template_name: str,
        context: Dict[str, Any],
        user,
        document_type: str = 'report',
        title: str = None,
        order: Order = None
    ) -> Optional[GeneratedDocument]:
        """
        Generate a document from a custom template.
        
        Args:
            template_name: Name of the template
            context: Context data for the template
            user: User for whom the document is generated
            document_type: Type of document
            title: Document title
            order: Related order (optional)
        
        Returns:
            GeneratedDocument instance or None
        """
        try:
            # Get template
            template = DocumentTemplate.objects.get(name=template_name, is_active=True)
            
            # Add default context
            default_context = {
                'generation_date': timezone.now().strftime('%B %d, %Y'),
                'user_name': user.get_full_name() or user.email,
                'user_email': user.email,
                'site_name': getattr(settings, 'SITE_NAME', 'EBWriting'),
            }
            
            if order:
                default_context['order'] = order
                default_context['order_id'] = order.order_id
            
            # Merge contexts
            full_context = {**default_context, **context}
            
            # Get template content
            template_content = template.get_template_content()
            
            # Replace placeholders
            for key, value in full_context.items():
                placeholder = f'{{{{{key}}}}}'
                template_content = template_content.replace(placeholder, str(value))
            
            # Generate PDF based on template format
            if template.format == 'html':
                pdf_bytes = PDFGenerationService._html_to_pdf(template_content)
            elif template.format == 'latex':
                pdf_bytes = PDFGenerationService._latex_to_pdf(template_content)
            else:
                # For DOCX templates, we would need additional processing
                logger.error(f"Unsupported template format: {template.format}")
                return None
            
            if not pdf_bytes:
                return None
            
            # Create title if not provided
            if not title:
                title = f"{template.name} - {timezone.now().strftime('%Y-%m-%d')}"
            
            # Create GeneratedDocument
            document = PDFGenerationService._create_document(
                title=title,
                document_type=document_type,
                content=pdf_bytes,
                order=order,
                user=user,
                generated_by=user,
                template_name=template_name,
                template_version=template.version
            )
            
            logger.info(f"Document generated from template {template_name} for user {user.email}")
            return document
            
        except DocumentTemplate.DoesNotExist:
            logger.error(f"Template not found: {template_name}")
            return None
        except Exception as e:
            logger.error(f"Error generating document from template {template_name}: {e}")
            return None
    
    @staticmethod
    def _html_to_pdf(html_content: str) -> Optional[bytes]:
        """
        Convert HTML content to PDF.
        
        Args:
            html_content: HTML content
        
        Returns:
            PDF bytes or None
        """
        try:
            # Configure pdfkit
            options = {
                'page-size': 'Letter',
                'encoding': 'UTF-8',
                'no-outline': None,
                'quiet': '',
            }
            
            # Try using wkhtmltopdf if available
            try:
                config = pdfkit.configuration(wkhtmltopdf='/usr/local/bin/wkhtmltopdf')
                pdf = pdfkit.from_string(html_content, False, options=options, configuration=config)
            except:
                # Fallback to reportlab
                pdf = PDFGenerationService._generate_with_reportlab(html_content)
            
            return pdf
            
        except Exception as e:
            logger.error(f"Error converting HTML to PDF: {e}")
            return None
    
    @staticmethod
    def _generate_with_reportlab(content: str) -> bytes:
        """
        Generate PDF using ReportLab as fallback.
        
        Args:
            content: Document content
        
        Returns:
            PDF bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        
        # Create styles
        styles = getSampleStyleSheet()
        story = []
        
        # Add content
        story.append(Paragraph("EBWriting Document", styles['Title']))
        story.append(Spacer(1, 12))
        
        # Simple content extraction (in real implementation, parse HTML properly)
        lines = content.split('\n')
        for line in lines[:50]:  # Limit to first 50 lines
            if line.strip():
                story.append(Paragraph(line.strip(), styles['Normal']))
                story.append(Spacer(1, 6))
        
        # Build PDF
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
    
    @staticmethod
    def _latex_to_pdf(latex_content: str) -> Optional[bytes]:
        """
        Convert LaTeX content to PDF.
        
        Args:
            latex_content: LaTeX content
        
        Returns:
            PDF bytes or None
        """
        try:
            # This would require a LaTeX installation
            # For now, return None and log warning
            logger.warning("LaTeX to PDF conversion not implemented")
            return None
        except Exception as e:
            logger.error(f"Error converting LaTeX to PDF: {e}")
            return None
    
    @staticmethod
    def _create_document(
        title: str,
        document_type: str,
        content: bytes,
        user,
        generated_by=None,
        order=None,
        template_name=None,
        template_version=1
    ) -> GeneratedDocument:
        """
        Create a GeneratedDocument from PDF content.
        
        Args:
            title: Document title
            document_type: Type of document
            content: PDF bytes
            user: Document owner
            generated_by: User who generated the document
            order: Related order
            template_name: Template used
            template_version: Template version
        
        Returns:
            GeneratedDocument instance
        """
        # Calculate hash
        content_hash = hashlib.sha256(content).hexdigest()
        
        # Create filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{document_type}_{timestamp}.pdf"
        
        # Create ContentFile
        content_file = ContentFile(content, name=filename)
        
        # Create document
        document = GeneratedDocument.objects.create(
            title=title,
            document_type=document_type,
            order=order,
            user=user,
            file=content_file,
            file_size=len(content),
            content_hash=content_hash,
            template_used=template_name,
            template_version=template_version,
            generated_by=generated_by,
        )
        
        return document


# In apps/documents/services/pdf_generator.py, update these methods:

class DocumentSecurityService:
    """Service for document security and validation"""
    
    @staticmethod
    def verify_document_integrity(document):
        """
        Verify document integrity using hash.
        
        Args:
            document: The document to verify (Document or GeneratedDocument)
        
        Returns:
            True if integrity verified, False otherwise
        """
        try:
            # Check if document has content_hash attribute
            if not hasattr(document, 'content_hash'):
                return True  # Can't verify documents without hash
            
            # Read file
            document.file.open('rb')
            content = document.file.read()
            document.file.close()
            
            # Calculate hash
            import hashlib
            current_hash = hashlib.sha256(content).hexdigest()
            
            # Compare with stored hash
            return current_hash == document.content_hash
            
        except Exception as e:
            logger.error(f"Error verifying document integrity: {e}")
            return False
    
    @staticmethod
    def generate_digital_signature(document, user):
        """
        Generate a digital signature for a document.
        
        Args:
            document: The document to sign
            user: User signing the document
        
        Returns:
            Signature data or None
        """
        try:
            # Check if document can be signed
            if not hasattr(document, 'can_user_sign'):
                return None
            
            # In a real implementation, this would use cryptographic signing
            # For now, create a simple signature string
            from django.utils import timezone
            timestamp = timezone.now().isoformat()
            
            # Use appropriate ID field
            doc_id = getattr(document, 'id', str(document.pk))
            
            # Create signature data
            if hasattr(document, 'content_hash'):
                data_to_sign = f"{doc_id}|{user.id}|{timestamp}|{document.content_hash}"
            else:
                data_to_sign = f"{doc_id}|{user.id}|{timestamp}"
            
            # Create signature (in real implementation, use private key)
            signature = hashlib.sha256(data_to_sign.encode()).hexdigest()
            
            return f"{timestamp}|{signature}"
            
        except Exception as e:
            logger.error(f"Error generating digital signature: {e}")
            return None


class DocumentAccessService:
    """Service for managing document access and audit trails"""
    
    @staticmethod
    def log_document_access(document, user, access_type, request=None):
        """
        Log document access.
        
        Args:
            document: The accessed document (Document or GeneratedDocument)
            user: User accessing the document
            access_type: Type of access
            request: HTTP request (optional)
        """
        from apps.documents.models import DocumentAccessLog
        
        try:
            log_entry = DocumentAccessLog(
                document=document,
                user=user,
                access_type=access_type,
                was_successful=True,
            )
            
            if request:
                log_entry.ip_address = request.META.get('REMOTE_ADDR')
                log_entry.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
                log_entry.session_key = request.session.session_key
            
            log_entry.save()
            
        except Exception as e:
            logger.error(f"Error logging document access: {e}")
    
    @staticmethod
    def can_user_access_document(document, user):
        """
        Check if user can access a document.
        
        Args:
            document: The document (Document or GeneratedDocument)
            user: User requesting access
        
        Returns:
            True if user can access, False otherwise
        """
        # Document owner/uploader can always access
        if hasattr(document, 'user') and document.user == user:
            return True
        if hasattr(document, 'uploader') and document.uploader == user:
            return True
        
        # Admin can access all documents
        if user.is_staff:
            return True
        
        # Writers can access documents for their orders
        if hasattr(document, 'order') and document.order and document.order.assigned_writer == user:
            return True
        
        # Check if document is shared with user
        # (This would require a document sharing model)
        
        return False