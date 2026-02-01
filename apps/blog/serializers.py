from rest_framework import serializers
from django.contrib.auth import get_user_model
from taggit.serializers import TagListSerializerField, TaggitSerializer

from .models import BlogCategory, BlogPost, BlogComment, SEOAuditLog, BlogSubscription

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'profile_picture']


class BlogCategorySerializer(serializers.ModelSerializer):
    """Serializer for blog categories"""
    post_count = serializers.IntegerField(source='posts.count', read_only=True)
    
    class Meta:
        model = BlogCategory
        fields = ['id', 'name', 'slug', 'description', 'post_count', 'is_active']
        read_only_fields = ['slug']


class BlogPostSerializer(TaggitSerializer, serializers.ModelSerializer):
    """Serializer for blog posts"""
    author = UserSerializer(read_only=True)
    category = BlogCategorySerializer(read_only=True)
    tags = TagListSerializerField()
    
    # Computed fields
    reading_time = serializers.IntegerField(source='reading_time_minutes', read_only=True)
    absolute_url = serializers.CharField(source='get_absolute_url', read_only=True)
    
    # SEO fields
    meta_title = serializers.CharField(required=False, allow_blank=True)
    meta_description = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'excerpt', 'content', 'featured_image',
            'author', 'category', 'status', 'tags',
            'meta_title', 'meta_description', 'meta_keywords',
            'reading_time', 'word_count', 'view_count', 'share_count',
            'canonical_url', 'published_at', 'created_at', 'updated_at',
            'absolute_url'
        ]
        read_only_fields = [
            'id', 'slug', 'author', 'word_count', 'reading_time',
            'view_count', 'share_count', 'created_at', 'updated_at'
        ]
    
    def validate_content(self, value):
        """Validate content length"""
        if len(value.split()) < 300:
            raise serializers.ValidationError(
                "Content must be at least 300 words."
            )
        return value
    
    def create(self, validated_data):
        """Create a new blog post"""
        tags = validated_data.pop('tags', [])
        
        # Set author from request user
        validated_data['author'] = self.context['request'].user
        
        post = BlogPost.objects.create(**validated_data)
        post.tags.set(tags)
        
        return post
    
    def update(self, instance, validated_data):
        """Update an existing blog post"""
        tags = validated_data.pop('tags', None)
        
        # Update post fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Update tags if provided
        if tags is not None:
            instance.tags.set(tags)
        
        return instance


class BlogCommentSerializer(serializers.ModelSerializer):
    """Serializer for blog comments"""
    user = UserSerializer(read_only=True)
    post = serializers.SlugRelatedField(
        slug_field='slug',
        queryset=BlogPost.objects.filter(status=BlogPost.PostStatus.PUBLISHED)
    )
    
    # Computed fields
    display_name = serializers.CharField(read_only=True)
    is_staff_comment = serializers.SerializerMethodField()
    
    class Meta:
        model = BlogComment
        fields = [
            'id', 'post', 'user', 'guest_name', 'guest_email',
            'content', 'status', 'display_name', 'is_staff_comment',
            'upvotes', 'downvotes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'display_name', 'is_staff_comment',
            'upvotes', 'downvotes', 'created_at', 'updated_at'
        ]
    
    def get_is_staff_comment(self, obj):
        """Check if comment is from staff"""
        return obj.user.is_staff if obj.user else False
    
    def validate(self, data):
        """Validate comment data"""
        # Either user or guest information must be provided
        request = self.context.get('request')
        
        if not request.user.is_authenticated:
            if not data.get('guest_name') or not data.get('guest_email'):
                raise serializers.ValidationError(
                    "Guest name and email are required for anonymous comments."
                )
        
        return data


class SEOAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for SEO audit logs"""
    performed_by = UserSerializer(read_only=True)
    post = serializers.SlugRelatedField(
        slug_field='slug',
        queryset=BlogPost.objects.all()
    )
    
    class Meta:
        model = SEOAuditLog
        fields = [
            'id', 'post', 'audit_type', 'readability_score',
            'keyword_density', 'heading_structure', 'meta_score',
            'issues_found', 'recommendations', 'applied_fixes',
            'performed_by', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BlogSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for blog subscriptions"""
    class Meta:
        model = BlogSubscription
        fields = [
            'id', 'email', 'is_active', 'receive_new_posts',
            'receive_weekly_digest', 'categories', 'subscribed_at'
        ]
        read_only_fields = ['id', 'is_active', 'subscribed_at']
    
    def validate_email(self, value):
        """Validate email"""
        # Check if already subscribed
        if BlogSubscription.objects.filter(
            email=value, 
            is_active=True
        ).exists():
            raise serializers.ValidationError(
                "This email is already subscribed."
            )
        
        return value


class SEOAnalyzeSerializer(serializers.Serializer):
    """Serializer for SEO analysis input"""
    content = serializers.CharField(required=True)
    title = serializers.CharField(required=False, allow_blank=True)
    meta_description = serializers.CharField(required=False, allow_blank=True)
    keywords = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=[]
    )
    
    def validate_content(self, value):
        """Validate content"""
        if len(value.strip()) < 100:
            raise serializers.ValidationError(
                "Content must be at least 100 characters."
            )
        return value