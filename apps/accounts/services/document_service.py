import os
from typing import Dict, Optional
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings

from apps.accounts.models import WriterDocument
from .document_validator import DocumentValidator


class DocumentService:
    """Service for managing writer document operations."""
    
    @classmethod
    @transaction.atomic
    def upload_document(
        cls,
        user,
        document_type: str,
        file_obj,
        **metadata
    ) -> WriterDocument:
        """
        Upload and validate a writer document.
        
        Args:
            user: User uploading the document
            document_type: Type of document (from WriterDocument.DocumentType)
            file_obj: Uploaded file object
            **metadata: Additional metadata
            
        Returns:
            Created WriterDocument object
        
        Raises:
            ValidationError: If document fails validation
        """
        # Validate filename safety
        if not DocumentValidator.is_safe_filename(file_obj.name):
            raise ValidationError("Invalid filename.")
        
        # Validate file
        validation_result = DocumentValidator.validate_file(file_obj)
        
        # Create document record
        document = WriterDocument(
            user=user,
            document_type=document_type,
            original_filename=validation_result['original_filename'],
            file_size=validation_result['file_size'],
            mime_type=validation_result['mime_type'],
            file_hash=validation_result['file_hash'],
            **metadata
        )
        
        # Perform virus scan
        if hasattr(settings, 'ENABLE_VIRUS_SCAN') and settings.ENABLE_VIRUS_SCAN:
            # Save file temporarily for scanning
            temp_path = f'temp/{timezone.now().timestamp()}_{file_obj.name}'
            with default_storage.open(temp_path, 'wb') as temp_file:
                for chunk in file_obj.chunks():
                    temp_file.write(chunk)
            
            # Scan file
            is_clean, scan_result = DocumentValidator.virus_scan_file(
                default_storage.path(temp_path)
            )
            
            document.scanned_for_virus = True
            document.scan_result = scan_result
            
            # Delete temporary file
            default_storage.delete(temp_path)
            
            if not is_clean:
                raise ValidationError(f"File failed virus scan: {scan_result}")
        
        # Validate business logic
        document.clean()
        
        # Save document
        document.document.save(file_obj.name, file_obj, save=False)
        document.save()
        
        # Check if user can transition to documents_submitted state
        cls._check_document_completion(user)
        
        return document
    
    @classmethod
    def _check_document_completion(cls, user):
        """Check if user has enough documents to submit for verification."""
        from apps.accounts.services.verification_service import VerificationService
        
        verification = user.verification_status
        
        if verification.state != 'profile_completed':
            return
        
        # Count verified documents
        verified_count = user.documents.filter(status='verified').count()
        
        # Minimum 3 verified documents required
        if verified_count >= 3:
            try:
                VerificationService.submit_for_verification(user)
            except ValidationError:
                # Silently fail - user can manually submit later
                pass
    
    @classmethod
    def verify_document(
        cls,
        document_id: int,
        admin_user,
        notes: str = '',
        expires_in_days: int = 365
    ) -> WriterDocument:
        """
        Verify a document (admin action).
        
        Args:
            document_id: ID of the document to verify
            admin_user: Admin user performing verification
            notes: Verification notes
            expires_in_days: Days until document expires
            
        Returns:
            Updated WriterDocument object
        """
        if not admin_user.is_staff:
            raise PermissionError("Only staff can verify documents.")
        
        document = WriterDocument.objects.get(id=document_id)
        
        document.status = WriterDocument.DocumentStatus.VERIFIED
        document.reviewed_by = admin_user
        document.review_notes = notes
        document.verified_at = timezone.now()
        document.expires_at = timezone.now() + timezone.timedelta(days=expires_in_days)
        document.save()
        
        return document
    
    @classmethod
    def reject_document(
        cls,
        document_id: int,
        admin_user,
        reason: str
    ) -> WriterDocument:
        """
        Reject a document (admin action).
        
        Args:
            document_id: ID of the document to reject
            admin_user: Admin user performing rejection
            reason: Reason for rejection
            
        Returns:
            Updated WriterDocument object
        """
        if not admin_user.is_staff:
            raise PermissionError("Only staff can reject documents.")
        
        document = WriterDocument.objects.get(id=document_id)
        
        document.status = WriterDocument.DocumentStatus.REJECTED
        document.reviewed_by = admin_user
        document.rejection_reason = reason
        document.save()
        
        return document
    
    @classmethod
    def get_document_stats(cls, user_id: Optional[int] = None) -> Dict:
        """
        Get document statistics.
        
        Args:
            user_id: Optional user ID to filter by
            
        Returns:
            Dictionary with document statistics
        """
        queryset = WriterDocument.objects.all()
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        stats = {
            'total': queryset.count(),
            'by_status': {},
            'by_type': {},
            'expiring_soon': 0,
        }
        
        # Count by status
        for status_code, status_name in WriterDocument.DocumentStatus.choices:
            count = queryset.filter(status=status_code).count()
            stats['by_status'][status_code] = {
                'count': count,
                'name': status_name,
            }
        
        # Count by type
        for type_code, type_name in WriterDocument.DocumentType.choices:
            count = queryset.filter(document_type=type_code).count()
            stats['by_type'][type_code] = {
                'count': count,
                'name': type_name,
            }
        
        # Count expiring soon (within 30 days)
        thirty_days_from_now = timezone.now() + timezone.timedelta(days=30)
        stats['expiring_soon'] = queryset.filter(
            expires_at__lte=thirty_days_from_now,
            status=WriterDocument.DocumentStatus.VERIFIED
        ).count()
        
        return stats
    
    @classmethod
    def cleanup_expired_documents(cls) -> int:
        """
        Mark expired documents as expired.
        
        Returns:
            Number of documents updated
        """
        now = timezone.now()
        
        expired_docs = WriterDocument.objects.filter(
            expires_at__lt=now,
            status=WriterDocument.DocumentStatus.VERIFIED
        )
        
        count = expired_docs.count()
        
        for doc in expired_docs:
            doc.status = WriterDocument.DocumentStatus.EXPIRED
            doc.save()
        
        return count