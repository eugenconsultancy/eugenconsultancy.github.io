"""
Admin configuration for the Documents app.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from apps.documents.models import (
    GeneratedDocument, DocumentTemplate, DocumentSignature, DocumentAccessLog
)


@admin.register(GeneratedDocument)
class GeneratedDocumentAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'document_type', 'user_email', 'order_id',
        'file_size_mb', 'is_signed', 'is_archived', 'generated_at', 'download_link'
    ]
    list_filter = [
        'document_type', 'is_signed', 'is_archived',
        'generated_at', 'template_used'
    ]
    search_fields = ['title', 'user__email', 'order__order_id']
    readonly_fields = [
        'generated_at', 'created_at', 'updated_at',
        'signed_at', 'archived_at', 'file_size',
        'content_hash', 'template_version'
    ]
    list_select_related = ['user', 'order']
    date_hierarchy = 'generated_at'
    actions = ['archive_documents', 'verify_signatures']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def order_id(self, obj):
        if obj.order:
            return obj.order.order_id
        return 'N/A'
    order_id.short_description = 'Order ID'
    
    def file_size_mb(self, obj):
        if obj.file_size:
            return f"{obj.file_size / 1024 / 1024:.2f} MB"
        return 'N/A'
    file_size_mb.short_description = 'Size'
    
    def download_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">Download</a>', obj.file.url)
        return 'No file'
    download_link.short_description = 'File'
    
    def archive_documents(self, request, queryset):
        for document in queryset:
            document.archive(archived_by=request.user)
        self.message_user(request, f'{queryset.count()} documents archived.')
    archive_documents.short_description = 'Archive selected documents'
    
    def verify_signatures(self, request, queryset):
        from apps.documents.services.pdf_generator import DocumentSecurityService
        for document in queryset:
            if document.is_signed:
                is_valid = DocumentSecurityService.verify_digital_signature(document)
                if not is_valid:
                    self.message_user(request, f'Invalid signature for document: {document.title}')
        self.message_user(request, f'{queryset.count()} signatures verified.')
    verify_signatures.short_description = 'Verify digital signatures'


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'template_type', 'format', 'version',
        'is_active', 'requires_signature', 'updated_at'
    ]
    list_filter = ['template_type', 'format', 'is_active', 'requires_signature']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_active', 'version']
    filter_horizontal = []
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ['name', 'template_type', 'format']
        return self.readonly_fields


@admin.register(DocumentSignature)
class DocumentSignatureAdmin(admin.ModelAdmin):
    list_display = [
        'document_title', 'signed_by_email', 'signed_at',
        'is_valid', 'verified_at', 'certificate_expiry'
    ]
    list_filter = ['is_valid', 'signed_at', 'verified_at']
    search_fields = ['document__title', 'signed_by__email']
    readonly_fields = [
        'signed_at', 'verified_at', 'created_at',
        'signature_hash', 'certificate_expiry'
    ]
    list_select_related = ['document', 'signed_by', 'verified_by']
    actions = ['verify_signatures']
    
    def document_title(self, obj):
        return obj.document.title
    document_title.short_description = 'Document'
    
    def signed_by_email(self, obj):
        return obj.signed_by.email
    signed_by_email.short_description = 'Signed By'
    
    def verify_signatures(self, request, queryset):
        for signature in queryset:
            if not signature.is_valid:
                signature.verify(verified_by=request.user)
        self.message_user(request, f'{queryset.count()} signatures verified.')
    verify_signatures.short_description = 'Verify selected signatures'


@admin.register(DocumentAccessLog)
class DocumentAccessLogAdmin(admin.ModelAdmin):
    list_display = [
        'document_title', 'user_email', 'access_type',
        'ip_address', 'was_successful', 'accessed_at'
    ]
    list_filter = ['access_type', 'was_successful', 'accessed_at']
    search_fields = ['document__title', 'user__email', 'ip_address']
    # FIXED: Removed 'created_at' as it was not defined in the model; used 'accessed_at'
    readonly_fields = ['accessed_at']
    list_select_related = ['document', 'user']
    date_hierarchy = 'accessed_at'
    
    def document_title(self, obj):
        return obj.document.title
    document_title.short_description = 'Document'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False