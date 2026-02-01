# apps/notifications/views.py
import logging
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics
from rest_framework.pagination import PageNumberPagination
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from apps.notifications.models import (
    Notification, 
    NotificationPreference,
    NotificationLog
)
from apps.notifications.services import (
    NotificationService,
    NotificationAnalyticsService
)
from apps.notifications.serializers import (
    NotificationSerializer,
    NotificationPreferenceSerializer,
    NotificationLogSerializer,
    UpdatePreferenceSerializer
)

logger = logging.getLogger(__name__)


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class NotificationListView(generics.ListAPIView):
    """
    List all notifications for the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination
    
    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(user=user).order_by('-created_at')
        
        # Apply filters
        status_filter = self.request.query_params.get('status')
        if status_filter == 'read':
            queryset = queryset.filter(is_read=True)
        elif status_filter == 'unread':
            queryset = queryset.filter(is_read=False)
        
        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(notification_type=type_filter)
        
        # Date range filter
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        
        # Add summary statistics
        user = request.user
        unread_count = NotificationService.get_unread_count(user)
        total_count = Notification.objects.filter(user=user).count()
        
        response.data['summary'] = {
            'total_notifications': total_count,
            'unread_notifications': unread_count
        }
        
        return response


class UnreadNotificationListView(generics.ListAPIView):
    """
    List only unread notifications for the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user,
            is_read=False
        ).order_by('-created_at')


class MarkAsReadView(APIView):
    """
    Mark a specific notification as read.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, notification_id):
        try:
            success = NotificationService.mark_notification_as_read(
                notification_id=notification_id,
                user=request.user
            )
            
            if success:
                return Response(
                    {'status': 'Notification marked as read'},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {'error': 'Notification not found or not authorized'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
        except Exception as e:
            logger.error(f"Error marking notification {notification_id} as read: {e}")
            return Response(
                {'error': 'Failed to mark notification as read'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MarkAllAsReadView(APIView):
    """
    Mark all notifications as read for the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            count = NotificationService.mark_all_as_read(request.user)
            
            return Response(
                {
                    'status': f'{count} notifications marked as read',
                    'count': count
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error marking all notifications as read for {request.user.email}: {e}")
            return Response(
                {'error': 'Failed to mark notifications as read'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NotificationPreferencesView(generics.RetrieveUpdateAPIView):
    """
    View and update notification preferences.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationPreferenceSerializer
    
    def get_object(self):
        # Get or create preferences for user
        preferences, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return preferences


class UpdatePreferencesView(APIView):
    """
    Update specific notification preferences.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = UpdatePreferenceSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get user preferences
            preferences, created = NotificationPreference.objects.get_or_create(
                user=request.user
            )
            
            # Update preferences
            data = serializer.validated_data
            
            if 'email_enabled' in data:
                preferences.email_enabled = data['email_enabled']
            
            if 'push_enabled' in data:
                preferences.push_enabled = data['push_enabled']
            
            if 'sms_enabled' in data:
                preferences.sms_enabled = data['sms_enabled']
            
            if 'quiet_hours_enabled' in data:
                preferences.quiet_hours_enabled = data['quiet_hours_enabled']
            
            if 'quiet_hours_start' in data:
                preferences.quiet_hours_start = data['quiet_hours_start']
            
            if 'quiet_hours_end' in data:
                preferences.quiet_hours_end = data['quiet_hours_end']
            
            if 'preferences' in data:
                # Merge existing preferences with new ones
                existing_prefs = preferences.preferences
                existing_prefs.update(data['preferences'])
                preferences.preferences = existing_prefs
            
            preferences.save()
            
            return Response(
                {'status': 'Preferences updated successfully'},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error updating preferences for {request.user.email}: {e}")
            return Response(
                {'error': 'Failed to update preferences'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UnsubscribeDigestView(APIView):
    """
    Unsubscribe from daily digest emails.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            # Get user preferences
            preferences, created = NotificationPreference.objects.get_or_create(
                user=request.user
            )
            
            # Update daily digest preference
            prefs = preferences.preferences
            prefs['daily_digest'] = False
            preferences.preferences = prefs
            preferences.save()
            
            logger.info(f"Daily digest unsubscribed for {request.user.email}")
            
            return Response(
                {'status': 'Unsubscribed from daily digest'},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error unsubscribing digest for {request.user.email}: {e}")
            return Response(
                {'error': 'Failed to unsubscribe'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TestNotificationView(APIView):
    """
    Send a test notification (for debugging).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def post(self, request):
        try:
            # Create test notification
            notification = NotificationService.create_notification(
                user=request.user,
                title="Test Notification",
                message="This is a test notification sent from the admin panel.",
                notification_type='info',
                channels='all',
                priority=2,
                action_url='/notifications',
                action_text='View Notifications'
            )
            
            return Response(
                {
                    'status': 'Test notification sent',
                    'notification_id': str(notification.id)
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error sending test notification: {e}")
            return Response(
                {'error': 'Failed to send test notification'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NotificationAnalyticsView(APIView):
    """
    Get notification analytics (admin only).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def get(self, request):
        try:
            # Get query parameters
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            # Get delivery statistics
            stats = NotificationAnalyticsService.get_delivery_stats(
                start_date=start_date,
                end_date=end_date
            )
            
            return Response(stats, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting notification analytics: {e}")
            return Response(
                {'error': 'Failed to get analytics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserEngagementView(APIView):
    """
    Get user engagement statistics (admin only).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def get(self, request):
        try:
            user_id = request.query_params.get('user_id')
            days = int(request.query_params.get('days', 30))
            
            if not user_id:
                return Response(
                    {'error': 'user_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            user = get_object_or_404(User, id=user_id)
            
            # Get engagement statistics
            engagement_stats = NotificationAnalyticsService.get_user_engagement(
                user=user,
                days=days
            )
            
            return Response(engagement_stats, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting user engagement stats: {e}")
            return Response(
                {'error': 'Failed to get engagement statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NotificationLogListView(generics.ListAPIView):
    """
    List notification logs (admin only).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = NotificationLogSerializer
    pagination_class = NotificationPagination
    
    def get_queryset(self):
        queryset = NotificationLog.objects.all().order_by('-created_at')
        
        # Apply filters
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        channel_filter = self.request.query_params.get('channel')
        if channel_filter:
            queryset = queryset.filter(channel=channel_filter)
        
        email_filter = self.request.query_params.get('email')
        if email_filter:
            queryset = queryset.filter(recipient_email__icontains=email_filter)
        
        # Date range filter
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        
        # Add summary statistics
        total = NotificationLog.objects.count()
        sent = NotificationLog.objects.filter(status='sent').count()
        failed = NotificationLog.objects.filter(status='failed').count()
        
        response.data['summary'] = {
            'total_logs': total,
            'sent_logs': sent,
            'failed_logs': failed,
            'success_rate': (sent / total * 100) if total > 0 else 0
        }
        
        return response