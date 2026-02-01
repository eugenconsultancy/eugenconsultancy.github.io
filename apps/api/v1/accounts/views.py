"""
API views for accounts app.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from apps.accounts.models import WriterProfile
from .serializers import UserSerializer, WriterProfileSerializer
from apps.api.permissions import IsAdminUser, IsOwnerOrAdmin, IsVerifiedWriter

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint for users.
    
    - Admin users can view and edit all users
    - Users can view and edit their own profile
    - Registration is handled by Djoser
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions for this view.
        """
        if self.action == 'create':
            # Allow registration
            permission_classes = [permissions.AllowAny]
        elif self.action in ['update', 'partial_update', 'destroy']:
            # Only allow users to modify their own profile or admin
            permission_classes = [IsOwnerOrAdmin]
        else:
            # List and retrieve require authentication
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        if user.is_staff:
            return User.objects.all()
        else:
            # Users can only see their own profile
            return User.objects.filter(id=user.id)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """
        Get current user's profile.
        """
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsOwnerOrAdmin])
    def change_password(self, request, pk=None):
        """
        Change user password.
        """
        user = self.get_object()
        
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not old_password or not new_password:
            return Response(
                {'error': 'Both old and new password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not user.check_password(old_password):
            return Response(
                {'error': 'Old password is incorrect'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(new_password)
        user.save()
        
        return Response({'message': 'Password changed successfully'})


class WriterProfileViewSet(viewsets.ModelViewSet):
    """
    API endpoint for writer profiles.
    
    - Writers can view and edit their own profile
    - Admin can view and edit all profiles
    - Clients can view writer profiles (read-only)
    """
    queryset = WriterProfile.objects.all().select_related('user')
    serializer_class = WriterProfileSerializer
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions for this view.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Only writers can modify their profile, admin can do anything
            permission_classes = [IsOwnerOrAdmin | IsAdminUser]
        else:
            # List and retrieve are available to authenticated users
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        
        if user.is_staff:
            return WriterProfile.objects.all()
        elif user.role == User.Role.WRITER:
            # Writers can see their own profile
            return WriterProfile.objects.filter(user=user)
        else:
            # Clients can see verified writer profiles
            return WriterProfile.objects.filter(is_verified=True)
    
    def perform_create(self, serializer):
        """
        Set the user when creating a writer profile.
        """
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        """
        Verify a writer profile (admin only).
        """
        writer_profile = self.get_object()
        
        if writer_profile.is_verified:
            return Response(
                {'error': 'Writer is already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        writer_profile.is_verified = True
        writer_profile.verification_status = 'approved'
        writer_profile.save()
        
        # Send notification to writer
        from apps.notifications.tasks import send_notification
        send_notification.delay(
            user_id=writer_profile.user_id,
            notification_type='writer_verified',
            title='Writer Profile Verified',
            message='Your writer profile has been verified. You can now accept orders.',
            related_object_type='writer_profile',
            related_object_id=str(writer_profile.id)
        )
        
        return Response({'message': 'Writer profile verified successfully'})
    
    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def statistics(self, request, pk=None):
        """
        Get writer statistics (orders completed, rating, etc.).
        """
        writer_profile = self.get_object()
        
        # Calculate statistics
        statistics = {
            'total_orders': writer_profile.completed_orders.count(),
            'average_rating': writer_profile.average_rating,
            'completion_rate': writer_profile.completion_rate,
            'revision_rate': writer_profile.revision_rate,
            'total_earnings': writer_profile.total_earnings,
        }
        
        return Response(statistics)