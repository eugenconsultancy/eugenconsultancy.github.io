"""
Serializers for plagiarism detection.
"""
from rest_framework import serializers
from django.utils import timezone

from .models import PlagiarismCheck, PlagiarismReport, PlagiarismPolicy
from apps.orders.models import Order
from apps.documents.models import Document


class PlagiarismCheckSerializer(serializers.ModelSerializer):
    """
    Serializer for plagiarism checks.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    risk_level = serializers.CharField(read_only=True)
    risk_level_display = serializers.SerializerMethodField(read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    checked_filename = serializers.CharField(source='checked_file.original_filename', read_only=True)
    
    class Meta:
        model = PlagiarismCheck
        fields = [
            'id', 'order', 'order_number', 'source', 'source_display',
            'status', 'status_display', 'similarity_score',
            'word_count', 'character_count', 'risk_level', 'risk_level_display',
            'checked_file', 'checked_filename', 'is_sensitive',
            'requested_at', 'started_at', 'completed_at',
            'requested_by', 'processed_by'
        ]
        read_only_fields = [
            'id', 'similarity_score', 'word_count', 'character_count',
            'risk_level', 'requested_at', 'started_at', 'completed_at',
            'requested_by', 'processed_by'
        ]
    
    def get_risk_level_display(self, obj):
        """
        Get formatted risk level display.
        """
        risk_level = obj.risk_level
        if risk_level == 'low':
            return 'Low Risk'
        elif risk_level == 'medium':
            return 'Medium Risk'
        elif risk_level == 'high':
            return 'High Risk'
        elif risk_level == 'critical':
            return 'Critical Risk'
        else:
            return 'Unknown'
    
    def to_representation(self, instance):
        """
        Custom representation to hide sensitive data for non-admin users.
        """
        data = super().to_representation(instance)
        
        # Check if user is admin
        request = self.context.get('request')
        if request and not request.user.is_staff:
            # Hide sensitive fields
            if instance.is_sensitive:
                data['similarity_score'] = None
                data['raw_result'] = {}
                data['highlights'] = {}
                data['sources'] = []
                data['is_sensitive'] = True
            else:
                # Only show summary for non-sensitive reports
                del data['raw_result']
                del data['highlights']
                del data['sources']
        
        return data


class CreatePlagiarismCheckSerializer(serializers.ModelSerializer):
    """
    Serializer for creating plagiarism checks.
    """
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    file_to_check = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.filter(document_type='delivery'),
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = PlagiarismCheck
        fields = ['order', 'source', 'file_to_check']
    
    def validate(self, data):
        """
        Validate plagiarism check creation.
        """
        order = data['order']
        source = data.get('source', 'internal')
        
        # Check available sources
        from .api_clients import PlagiarismClientFactory
        available_sources = PlagiarismClientFactory.get_available_clients()
        
        if source not in available_sources:
            raise serializers.ValidationError(
                f"Plagiarism source '{source}' is not available"
            )
        
        # Check if order has delivery files
        if not data.get('file_to_check'):
            delivery_files = order.files.filter(document_type='delivery')
            if not delivery_files.exists():
                raise serializers.ValidationError(
                    "No delivery files found for plagiarism check"
                )
        
        return data


class PlagiarismReportSerializer(serializers.ModelSerializer):
    """
    Serializer for plagiarism reports.
    """
    plagiarism_check_info = serializers.SerializerMethodField()
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = PlagiarismReport
        fields = [
            'id', 'plagiarism_check', 'plagiarism_check_info',
            'title', 'summary', 'access_key', 'is_encrypted',
            'view_count', 'last_viewed', 'last_viewed_by',
            'generated_at', 'expires_at', 'is_expired'
        ]
        read_only_fields = [
            'id', 'access_key', 'view_count', 'last_viewed',
            'last_viewed_by', 'generated_at', 'is_expired'
        ]
    
    def get_plagiarism_check_info(self, obj):
        """
        Get plagiarism check summary.
        """
        return {
            'id': str(obj.plagiarism_check.id),
            'similarity_score': obj.plagiarism_check.similarity_score,
            'risk_level': obj.plagiarism_check.risk_level,
            'source': obj.plagiarism_check.source
        }
    
    def to_representation(self, instance):
        """
        Custom representation based on user permissions.
        """
        data = super().to_representation(instance)
        
        # Check if user is admin
        request = self.context.get('request')
        if request and not request.user.is_staff:
            # Hide detailed analysis for non-admin users
            del data['detailed_analysis']
        
        return data


class PlagiarismPolicySerializer(serializers.ModelSerializer):
    """
    Serializer for plagiarism policies.
    """
    class Meta:
        model = PlagiarismPolicy
        fields = [
            'id', 'name', 'description',
            'warning_threshold', 'action_threshold', 'rejection_threshold',
            'warning_action', 'critical_action',
            'order_types', 'client_tiers',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """
        Validate policy thresholds.
        """
        warning = data.get('warning_threshold', self.instance.warning_threshold if self.instance else 10.0)
        action = data.get('action_threshold', self.instance.action_threshold if self.instance else 25.0)
        rejection = data.get('rejection_threshold', self.instance.rejection_threshold if self.instance else 50.0)
        
        if warning >= action:
            raise serializers.ValidationError(
                "Warning threshold must be less than action threshold"
            )
        
        if action >= rejection:
            raise serializers.ValidationError(
                "Action threshold must be less than rejection threshold"
            )
        
        return data