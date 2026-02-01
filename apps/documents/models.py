# apps/documents/models.py
import uuid
import os
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import FileExtensionValidator

from apps.orders.models import Order


class GeneratedDocument(models.Model):
    """
    System-generated documents (invoices, order summaries, etc.).
    """
    DOCUMENT_TYPES = [
        ('invoice', 'Invoice'),
        ('order_summary', 'Order Summary'),
        ('delivery_cover', 'Delivery Cover Page'),
        ('completion_certificate', 'Completion Certificate'),
        ('refund_receipt', 'Refund Receipt'),
        ('agreement', 'Service Agreement'),
        ('report', 'Report'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    
    # Related objects
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='generated_documents',
        null=True,
        blank=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='generated_documents'
    )
    
    # Document content and storage
    title = models.CharField(max_length=255)
    file = models.FileField(
        upload_to='generated_documents/%Y/%m/%d/',
        help_text="Generated document file (PDF)"
    )
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    
    # Content metadata
    content_hash = models.CharField(max_length=64, help_text="SHA-256 hash of document content")
    template_used = models.CharField(max_length=100, blank=True, null=True)
    template_version = models.IntegerField(default=1)
    
    # Generation metadata
    generated_at = models.DateTimeField(default=timezone.now)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents_generated'
    )
    
    # Security and validation
    is_signed = models.BooleanField(default=False)
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents_signed'
    )
    digital_signature = models.TextField(blank=True, null=True)
    
    # Status
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    
    # Audit trail
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-generated_at']
        verbose_name = 'Generated Document'
        verbose_name_plural = 'Generated Documents'
        indexes = [
            models.Index(fields=['document_type', 'generated_at']),
            models.Index(fields=['order', 'document_type']),
            models.Index(fields=['user', 'generated_at']),
            models.Index(fields=['is_archived', 'generated_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.document_type})"
    
    def save(self, *args, **kwargs):
        # Calculate file size
        if self.file and hasattr(self.file, 'size'):
            self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    def get_download_url(self):
        """Get download URL for the document"""
        return self.file.url if self.file else None
    
    def archive(self, archived_by=None):
        """Archive the document"""
        self.is_archived = True
        self.archived_at = timezone.now()
        if archived_by:
            self.archived_by = archived_by
        self.save(update_fields=['is_archived', 'archived_at', 'archived_by', 'updated_at'])
    
    def sign(self, signed_by, signature_data):
        """Digitally sign the document"""
        self.is_signed = True
        self.signed_at = timezone.now()
        self.signed_by = signed_by
        self.digital_signature = signature_data
        self.save(update_fields=[
            'is_signed', 'signed_at', 'signed_by',
            'digital_signature', 'updated_at'
        ])


class DocumentTemplate(models.Model):
    """
    Templates for generating documents.
    """
    TEMPLATE_FORMATS = [
        ('html', 'HTML'),
        ('latex', 'LaTeX'),
        ('docx', 'DOCX'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    
    # Template configuration
    template_type = models.CharField(max_length=50, choices=GeneratedDocument.DOCUMENT_TYPES)
    format = models.CharField(max_length=10, choices=TEMPLATE_FORMATS, default='html')
    template_file = models.FileField(
        upload_to='document_templates/',
        validators=[FileExtensionValidator(allowed_extensions=['html', 'tex', 'docx'])],
        blank=True,
        null=True
    )
    template_content = models.TextField(help_text="Template content (if not using file)")
    
    # Placeholder configuration
    placeholders = models.JSONField(
        default=list,
        help_text="List of available placeholders with descriptions and validation rules"
    )
    
    # Style configuration
    styles = models.JSONField(
        default=dict,
        help_text="CSS/styles for the template"
    )
    
    # Versioning
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    
    # Security
    requires_signature = models.BooleanField(default=False)
    allowed_signers = models.JSONField(
        default=list,
        help_text="List of user roles allowed to sign this document type"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='templates_created'
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Document Template'
        verbose_name_plural = 'Document Templates'
        indexes = [
            models.Index(fields=['template_type', 'is_active']),
            models.Index(fields=['is_active', 'version']),
        ]
    
    def __str__(self):
        return f"{self.name} v{self.version}"
    
    def get_template_content(self):
        """Get template content, either from file or field"""
        if self.template_file and self.template_file.file:
            try:
                return self.template_file.read().decode('utf-8')
            except:
                return self.template_content
        return self.template_content
    
    def can_user_sign(self, user):
        """Check if user can sign this document type"""
        if not self.requires_signature:
            return False
        
        # Check if user has required role
        user_roles = []
        if user.is_staff:
            user_roles.append('admin')
        if user.is_writer:
            user_roles.append('writer')
        if user.is_client:
            user_roles.append('client')
        
        return any(role in self.allowed_signers for role in user_roles)


class DocumentSignature(models.Model):
    """
    Digital signatures for documents.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(
        GeneratedDocument,
        on_delete=models.CASCADE,
        related_name='signature'
    )
    
    # Signature data
    signature_data = models.TextField()
    signature_hash = models.CharField(max_length=64, help_text="SHA-256 hash of signature")
    
    # Signer info
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='document_signatures'
    )
    signed_at = models.DateTimeField(default=timezone.now)
    
    # Verification info
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='signatures_verified'
    )
    is_valid = models.BooleanField(default=True)
    verification_notes = models.TextField(blank=True, null=True)
    
    # Certificate info (for advanced PKI)
    certificate_data = models.TextField(blank=True, null=True)
    certificate_expiry = models.DateTimeField(null=True, blank=True)
    
    # Audit trail
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = 'Document Signature'
        verbose_name_plural = 'Document Signatures'
        indexes = [
            models.Index(fields=['document', 'signed_at']),
            models.Index(fields=['signed_by', 'signed_at']),
            models.Index(fields=['is_valid', 'verified_at']),
        ]
    
    def __str__(self):
        return f"Signature for {self.document.title} by {self.signed_by.email}"
    
    def verify(self, verified_by=None):
        """Verify the signature"""
        # In a real implementation, this would verify the digital signature
        # For now, we'll mark it as verified
        self.verified_at = timezone.now()
        self.verified_by = verified_by
        self.is_valid = True
        self.save(update_fields=[
            'verified_at', 'verified_by', 'is_valid', 'updated_at'
        ])
# Add this Document model to the end of apps/documents/models.py (before the DocumentAccessLog class)

class Document(models.Model):
    """
    Generic uploaded document model for storing files.
    """
    DOCUMENT_TYPES = [
        ('order_file', 'Order File'),
        ('delivery', 'Delivery File'),
        ('revision_instruction', 'Revision Instruction'),
        ('revision_delivery', 'Revision Delivery'),
        ('writer_document', 'Writer Document'),
        ('profile_document', 'Profile Document'),
        ('invoice', 'Invoice'),
        ('report', 'Report'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    file = models.FileField(
        upload_to='documents/%Y/%m/%d/',
        help_text="Uploaded document file"
    )
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_documents'
    )
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES, default='other')
    
    # Related objects
    related_to = models.CharField(
        max_length=50,
        choices=[
            ('order', 'Order'),
            ('revision', 'Revision'),
            ('writer_profile', 'Writer Profile'),
            ('user_profile', 'User Profile'),
            ('other', 'Other'),
        ],
        default='other'
    )
    related_id = models.UUIDField(null=True, blank=True)
    
    # File metadata
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100, blank=True)
    original_filename = models.CharField(max_length=255)
    
    # Content metadata
    description = models.TextField(blank=True)
    
    # Security
    is_encrypted = models.BooleanField(default=False)
    encryption_key = models.TextField(blank=True, null=True, help_text="Encryption key (if encrypted)")
    
    # Status
    is_archived = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents_verified'
    )
    
    # Audit trail
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
        indexes = [
            models.Index(fields=['document_type', 'created_at']),
            models.Index(fields=['related_to', 'related_id']),
            models.Index(fields=['uploader', 'created_at']),
            models.Index(fields=['is_archived', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.document_type})"
    
    def save(self, *args, **kwargs):
        # Calculate file size and mime type
        if self.file and hasattr(self.file, 'size'):
            self.file_size = self.file.size
            
            # Try to get mime type
            try:
                import mimetypes
                self.mime_type = mimetypes.guess_type(str(self.file))[0] or 'application/octet-stream'
            except:
                self.mime_type = 'application/octet-stream'
        
        # Set original filename
        if self.file and not self.original_filename:
            self.original_filename = self.file.name.split('/')[-1]
            
        super().save(*args, **kwargs)
    
    def get_download_url(self):
        """Get download URL for the document"""
        return self.file.url if self.file else None
    
    def archive(self, archived_by=None):
        """Archive the document"""
        self.is_archived = True
        self.save(update_fields=['is_archived', 'updated_at'])
    
    def verify(self, verified_by):
        """Verify the document"""
        self.is_verified = True
        self.verified_at = timezone.now()
        self.verified_by = verified_by
        self.save(update_fields=['is_verified', 'verified_at', 'verified_by', 'updated_at'])

# Make sure this is placed above DocumentAccessLog class in the models.py file

# Update the DocumentAccessLog model in apps/documents/models.py
# Change the foreign key to reference Document instead of GeneratedDocument

class DocumentAccessLog(models.Model):
    """
    Audit log for document access.
    """
    ACCESS_TYPES = [
        ('view', 'View'),
        ('download', 'Download'),
        ('print', 'Print'),
        ('sign', 'Sign'),
        ('verify', 'Verify'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,  # Changed from GeneratedDocument to Document
        on_delete=models.CASCADE,
        related_name='access_logs'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='document_access_logs'
    )
    
    # Access details
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    # Session info
    session_key = models.CharField(max_length=40, blank=True, null=True)
    
    # Result
    was_successful = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)
    
    accessed_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-accessed_at']
        verbose_name = 'Document Access Log'
        verbose_name_plural = 'Document Access Logs'
        indexes = [
            models.Index(fields=['document', 'accessed_at']),
            models.Index(fields=['user', 'accessed_at']),
            models.Index(fields=['access_type', 'accessed_at']),
            models.Index(fields=['ip_address', 'accessed_at']),
        ]
    
    def __str__(self):
        return f"{self.access_type} of {self.document.name} by {self.user.email}"