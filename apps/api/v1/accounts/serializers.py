"""
Serializers for accounts app.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from apps.accounts.models import WriterProfile, WriterDocument

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model.
    """
    password = serializers.CharField(write_only=True, required=False)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'role', 'role_display',
            'is_active', 'is_staff', 'date_joined', 'last_login', 'password'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'is_staff']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}
        }
    
    def validate_password(self, value):
        """
        Validate password strength.
        """
        validate_password(value)
        return value
    
    def create(self, validated_data):
        """
        Create user with hashed password.
        """
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        
        if password:
            user.set_password(password)
            user.save()
        
        return user
    
    def update(self, instance, validated_data):
        """
        Update user, handling password separately.
        """
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class WriterDocumentSerializer(serializers.ModelSerializer):
    """
    Serializer for WriterDocument model.
    """
    class Meta:
        model = WriterDocument
        fields = [
            'id', 'document_type', 'original_filename', 'file_size',
            'uploaded_at', 'verified', 'verification_notes'
        ]
        read_only_fields = ['id', 'original_filename', 'file_size', 'uploaded_at']


class WriterProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for WriterProfile model.
    """
    user = UserSerializer(read_only=True)
    documents = WriterDocumentSerializer(many=True, read_only=True)
    verification_status_display = serializers.CharField(
        source='get_verification_status_display', 
        read_only=True
    )
    
    class Meta:
        model = WriterProfile
        fields = [
            'id', 'user', 'bio', 'specializations', 'education',
            'experience_years', 'hourly_rate', 'is_verified',
            'verification_status', 'verification_status_display',
            'average_rating', 'total_orders', 'completion_rate',
            'documents', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'is_verified', 'verification_status',
            'average_rating', 'total_orders', 'completion_rate',
            'created_at', 'updated_at'
        ]
    
    def validate_hourly_rate(self, value):
        """
        Validate hourly rate is positive.
        """
        if value < 0:
            raise serializers.ValidationError("Hourly rate must be positive")
        return value
    
    def validate_experience_years(self, value):
        """
        Validate experience years is non-negative.
        """
        if value < 0:
            raise serializers.ValidationError("Experience years must be non-negative")
        return value


class RegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    """
    password = serializers.CharField(write_only=True, required=True)
    password_confirm = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'role',
            'password', 'password_confirm'
        ]
    
    def validate(self, data):
        """
        Validate registration data.
        """
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match"})
        
        validate_password(data['password'])
        return data
    
    def create(self, validated_data):
        """
        Create user and associated profile if writer.
        """
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        
        # Create writer profile if user is a writer
        if user.role == User.Role.WRITER:
            WriterProfile.objects.create(user=user)
        
        return user