# apps/documents/serializers.py
from rest_framework import serializers
from django.utils import timezone

from apps.documents.models import (
    GeneratedDocument,
    DocumentTemplate,
    DocumentSignature
)
from apps.accounts.models import User
from apps.orders.models import Order


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details in documents."""
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for order details in documents."""
    
    class Meta:
        model = Order
        fields = ['order_id', 'title', 'total_amount', 'status']
        read_only_fields = fields


class GeneratedDocumentSerializer(serializers.ModelSerializer):
    """Serializer for generated documents."""
    
    user = UserSerializer(read_only=True)
    order = OrderSerializer(read_only=True)
    generated_by = UserSerializer(read_only=True)
    signed_by = UserSerializer(read_only=True)
    archived_by = UserSerializer(read_only=True)
    
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    download_url = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()
    integrity_status = serializers.SerializerMethodField()
    signature_status = serializers.SerializerMethodField()
    time_since = serializers.SerializerMethodField()
    
    class Meta:
        model = GeneratedDocument
        fields = [
            'id', 'document_type', 'document_type_display', 'title',
            'user', 'order', 'generated_by', 'signed_by', 'archived_by',
            'file_size', 'file_size_mb', 'download_url',
            'content_hash', 'template_used', 'template_version',
            'is_signed', 'signed_at', 'digital_signature',
            'is_archived', 'archived_at',
            'integrity_status', 'signature_status',
            'generated_at', 'created_at', 'updated_at', 'time_since'
        ]
        read_only_fields = fields
    
    def get_download_url(self, obj):
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(f'/documents/{obj.id}/download/')
        return None
    
    def get_file_size_mb(self, obj):
        if obj.file_size:
            return f"{obj.file_size / 1024 / 1024:.2f} MB"
        return None
    
    def get_integrity_status(self, obj):
        """Check document integrity."""
        from apps.documents.services import DocumentSecurityService
        try:
            return DocumentSecurityService.verify_document_integrity(obj)
        except:
            return False
    
    def get_signature_status(self, obj):
        """Check signature validity."""
        if not obj.is_signed:
            return 'not_signed'
        
        from apps.documents.services import DocumentSecurityService
        try:
            is_valid = DocumentSecurityService.verify_digital_signature(obj)
            return 'valid' if is_valid else 'invalid'
        except:
            return 'unknown'
    
    def get_time_since(self, obj):
        """Calculate time since document was generated."""
        delta = timezone.now() - obj.generated_at
        
        if delta.days > 365:
            years = delta.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"


class DocumentTemplateSerializer(serializers.ModelSerializer):
    """Serializer for document templates."""
    
    created_by = UserSerializer(read_only=True)
    template_type_display = serializers.CharField(source='get_template_type_display', read_only=True)
    format_display = serializers.CharField(source='get_format_display', read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentTemplate
        fields = [
            'id', 'name', 'description', 'template_type', 'template_type_display',
            'format', 'format_display', 'template_file', 'file_url', 'template_content',
            'placeholders', 'styles', 'version', 'is_active',
            'requires_signature', 'allowed_signers',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if request and obj.template_file:
            return request.build_absolute_uri(obj.template_file.url)
        return None
    
    def validate(self, data):
        """Validate template data."""
        # Ensure either template_file or template_content is provided
        if not data.get('template_file') and not data.get('template_content'):
            raise serializers.ValidationError(
                "Either template_file or template_content must be provided"
            )
        
        # Validate placeholders
        placeholders = data.get('placeholders', [])
        if not isinstance(placeholders, list):
            raise serializers.ValidationError("Placeholders must be a list")
        
        # Validate styles
        styles = data.get('styles', {})
        if not isinstance(styles, dict):
            raise serializers.ValidationError("Styles must be a JSON object")
        
        return data


class DocumentSignatureSerializer(serializers.ModelSerializer):
    """Serializer for document signatures."""
    
    document = GeneratedDocumentSerializer(read_only=True)
    signed_by = UserSerializer(read_only=True)
    verified_by = UserSerializer(read_only=True)
    
    time_since_signed = serializers.SerializerMethodField()
    time_since_verified = serializers.SerializerMethodField()
    certificate_status = serializers.SerializerMethodField()
    
    class Meta:
        model = DocumentSignature
        fields = [
            'id', 'document', 'signature_data', 'signature_hash',
            'signed_by', 'signed_at', 'time_since_signed',
            'verified_by', 'verified_at', 'time_since_verified',
            'is_valid', 'verification_notes',
            'certificate_data', 'certificate_expiry', 'certificate_status',
            'created_at'
        ]
        read_only_fields = fields
    
    def get_time_since_signed(self, obj):
        """Calculate time since signature was created."""
        if not obj.signed_at:
            return None
        
        delta = timezone.now() - obj.signed_at
        
        if delta.days > 365:
            years = delta.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    
    def get_time_since_verified(self, obj):
        """Calculate time since signature was verified."""
        if not obj.verified_at:
            return None
        
        delta = timezone.now() - obj.verified_at
        
        if delta.days > 365:
            years = delta.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    
    def get_certificate_status(self, obj):
        """Check certificate status."""
        if not obj.certificate_expiry:
            return 'no_certificate'
        
        if obj.certificate_expiry < timezone.now():
            return 'expired'
        
        days_until_expiry = (obj.certificate_expiry - timezone.now()).days
        if days_until_expiry <= 30:
            return 'expiring_soon'
        
        return 'valid'


class SignDocumentSerializer(serializers.Serializer):
    """Serializer for signing documents."""
    
    signature_data = serializers.CharField(required=False)
    verification_code = serializers.CharField(max_length=6, required=False)
    
    def validate(self, data):
        """Validate signing data."""
        # For now, we accept either signature_data or verification_code
        # In a real implementation, this would validate cryptographic signatures
        if not data.get('signature_data') and not data.get('verification_code'):
            raise serializers.ValidationError(
                "Either signature_data or verification_code must be provided"
            )
        return data