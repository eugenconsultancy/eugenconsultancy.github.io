import os
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import FileExtensionValidator


def writer_document_upload_path(instance, filename):
    """Generate upload path for writer documents."""
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    return os.path.join('writer_documents', str(instance.user.id), filename)


class WriterDocument(models.Model):
    """Documents submitted by writers for verification."""
    
    class DocumentType(models.TextChoices):
        ID_PROOF = 'id_proof', _('ID Proof')
        DEGREE_CERTIFICATE = 'degree_certificate', _('Degree Certificate')
        TRANSCRIPT = 'transcript', _('Academic Transcript')
        CV = 'cv', _('Curriculum Vitae')
        PORTFOLIO = 'portfolio', _('Writing Portfolio')
        OTHER = 'other', _('Other Document')
    
    class DocumentStatus(models.TextChoices):
        PENDING = 'pending', _('Pending Review')
        VERIFIED = 'verified', _('Verified')
        REJECTED = 'rejected', _('Rejected')
        EXPIRED = 'expired', _('Expired')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_('user')
    )
    
    document_type = models.CharField(
        _('document type'),
        max_length=50,
        choices=DocumentType.choices,
    )
    
    document = models.FileField(
        _('document file'),
        upload_to=writer_document_upload_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
            )
        ],
        help_text=_(
            'Upload PDF, JPG, PNG, DOC, or DOCX file. '
            'Maximum file size is 10MB.'
        )
    )
    
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.PENDING,
    )
    
    # Security & Verification
    file_hash = models.CharField(
        _('file hash'),
        max_length=128,
        blank=True,
        help_text=_('SHA-256 hash of the uploaded file for integrity verification')
    )
    
    scanned_for_virus = models.BooleanField(
        _('scanned for virus'),
        default=False,
    )
    
    scan_result = models.TextField(
        _('virus scan result'),
        blank=True,
        help_text=_('Result from virus scanning service')
    )
    
    # Metadata
    original_filename = models.CharField(
        _('original filename'),
        max_length=255,
    )
    
    file_size = models.PositiveIntegerField(
        _('file size in bytes'),
        help_text=_('Size of the uploaded file in bytes')
    )
    
    mime_type = models.CharField(
        _('MIME type'),
        max_length=100,
        blank=True,
    )
    
    # Verification Details
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_documents',
        verbose_name=_('reviewed by')
    )
    
    review_notes = models.TextField(
        _('review notes'),
        blank=True,
        help_text=_('Administrator notes regarding document verification')
    )
    
    rejection_reason = models.TextField(
        _('rejection reason'),
        blank=True,
        help_text=_('Reason for document rejection if applicable')
    )
    
    verified_at = models.DateTimeField(
        _('verified at'),
        null=True,
        blank=True,
    )
    
    expires_at = models.DateTimeField(
        _('expires at'),
        null=True,
        blank=True,
        help_text=_('Date when this document expires and needs renewal')
    )
    
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
    )
    
    class Meta:
        verbose_name = _('writer document')
        verbose_name_plural = _('writer documents')
        ordering = ['-created_at']
        unique_together = ['user', 'document_type', 'status']
        indexes = [
            models.Index(fields=['user', 'document_type']),
            models.Index(fields=['status']),
            models.Index(fields=['scanned_for_virus']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f'{self.get_document_type_display()} - {self.user.email}'
    
    def clean(self):
        """Validate document constraints."""
        from django.core.exceptions import ValidationError
        
        # Check file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if self.file_size > max_size:
            raise ValidationError(
                {'document': f'File size must be under {max_size/(1024*1024)}MB.'}
            )
        
        # Check for duplicate active documents of same type
        if self.status != self.DocumentStatus.REJECTED:
            existing = WriterDocument.objects.filter(
                user=self.user,
                document_type=self.document_type,
                status__in=[
                    self.DocumentStatus.PENDING,
                    self.DocumentStatus.VERIFIED
                ]
            ).exclude(pk=self.pk)
            
            if existing.exists():
                raise ValidationError(
                    f'You already have a {self.get_document_type_display()} '
                    'document pending or verified.'
                )
    
    @property
    def is_expired(self):
        """Check if document has expired."""
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self):
        """Check if document is currently valid."""
        return (
            self.status == self.DocumentStatus.VERIFIED
            and not self.is_expired
        )