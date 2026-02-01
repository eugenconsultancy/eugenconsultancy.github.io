import os
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator
from django.conf import settings


def order_file_upload_path(instance, filename):
    """Generate upload path for order files."""
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    return os.path.join('order_files', str(instance.order.id), filename)


class OrderFile(models.Model):
    """Files associated with orders (instructions, submissions, etc.)"""
    
    class FileType(models.TextChoices):
        INSTRUCTIONS = 'instructions', _('Instructions')
        REFERENCE = 'reference', _('Reference Material')
        SUBMISSION = 'submission', _('Submission')
        REVISION = 'revision', _('Revision')
        OTHER = 'other', _('Other')
    
    class FileStatus(models.TextChoices):
        UPLOADED = 'uploaded', _('Uploaded')
        PROCESSED = 'processed', _('Processed')
        REJECTED = 'rejected', _('Rejected')
    
    order = models.ForeignKey(
        'Order',
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name=_('order')
    )
    
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_files',
        verbose_name=_('uploaded by')
    )
    
    file_type = models.CharField(
        _('file type'),
        max_length=20,
        choices=FileType.choices,
        default=FileType.OTHER,
    )
    
    file = models.FileField(
        _('file'),
        upload_to=order_file_upload_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png', 'zip', 'rar']
            )
        ],
        help_text=_('Upload relevant order files (max 20MB)')
    )
    
    description = models.CharField(
        _('description'),
        max_length=500,
        blank=True,
        help_text=_('Brief description of the file contents')
    )
    
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=FileStatus.choices,
        default=FileStatus.UPLOADED,
    )
    
    # Security & Metadata
    file_hash = models.CharField(
        _('file hash'),
        max_length=128,
        blank=True,
        help_text=_('SHA-256 hash for integrity verification')
    )
    
    scanned_for_virus = models.BooleanField(
        _('scanned for virus'),
        default=False,
    )
    
    original_filename = models.CharField(
        _('original filename'),
        max_length=255,
    )
    
    file_size = models.PositiveIntegerField(
        _('file size in bytes'),
    )
    
    mime_type = models.CharField(
        _('MIME type'),
        max_length=100,
        blank=True,
    )
    
    # Versioning
    version = models.PositiveIntegerField(
        _('version'),
        default=1,
    )
    
    is_final = models.BooleanField(
        _('is final version'),
        default=False,
        help_text=_('Mark as final submission version')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
    )
    
    class Meta:
        verbose_name = _('order file')
        verbose_name_plural = _('order files')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'file_type']),
            models.Index(fields=['uploaded_by']),
            models.Index(fields=['status']),
            models.Index(fields=['is_final']),
        ]
    
    def __str__(self):
        return f'{self.get_file_type_display()} - Order #{self.order.order_number}'
    
    def clean(self):
        """Validate file constraints."""
        from django.core.exceptions import ValidationError
        
        # Check file size (20MB limit for order files)
        max_size = 20 * 1024 * 1024  # 20MB in bytes
        if self.file_size > max_size:
            raise ValidationError(
                f'File size must be under {max_size/(1024*1024)}MB.'
            )
        
        # Ensure only one final submission per order
        if self.file_type == self.FileType.SUBMISSION and self.is_final:
            existing_final = OrderFile.objects.filter(
                order=self.order,
                file_type=self.FileType.SUBMISSION,
                is_final=True
            ).exclude(pk=self.pk)
            
            if existing_final.exists():
                raise ValidationError(
                    'There is already a final submission for this order.'
                )
    
    @property
    def download_url(self):
        """Generate secure download URL."""
        # This would be implemented with signed URLs in production
        return f'/orders/{self.order.id}/files/{self.id}/download/'
    
    @property
    def is_submission(self):
        """Check if file is a submission."""
        return self.file_type == self.FileType.SUBMISSION
    
    @property
    def is_instructions(self):
        """Check if file contains instructions."""
        return self.file_type == self.FileType.INSTRUCTIONS