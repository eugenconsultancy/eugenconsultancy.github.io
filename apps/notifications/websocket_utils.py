# apps/notifications/websocket_utils.py
import json
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone

logger = logging.getLogger(__name__)


class WebSocketNotificationService:
    """Service for sending real-time notifications via WebSocket."""
    
    @staticmethod
    def send_notification_to_user(user_id, notification_data):
        """
        Send notification to specific user via WebSocket.
        
        Args:
            user_id: ID of the user to notify
            notification_data: Dictionary containing notification data
        """
        try:
            channel_layer = get_channel_layer()
            
            # Send to user's personal room
            async_to_sync(channel_layer.group_send)(
                f'notifications_user_{user_id}',
                {
                    'type': 'notification_created',
                    **notification_data
                }
            )
            
            # Also send to specific category room
            category = notification_data.get('category', 'system')
            async_to_sync(channel_layer.group_send)(
                f'notifications_user_{user_id}_{category}',
                {
                    'type': 'notification_created',
                    **notification_data
                }
            )
            
            logger.debug(f"WebSocket notification sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending WebSocket notification to user {user_id}: {e}")
    
    @staticmethod
    def send_order_update(user_id, order_data):
        """
        Send order update notification via WebSocket.
        
        Args:
            user_id: ID of the user to notify
            order_data: Dictionary containing order update data
        """
        try:
            channel_layer = get_channel_layer()
            
            async_to_sync(channel_layer.group_send)(
                f'notifications_user_{user_id}_order_updates',
                {
                    'type': 'order_update',
                    'timestamp': timezone.now().isoformat(),
                    **order_data
                }
            )
            
            logger.debug(f"Order update sent via WebSocket to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending order update via WebSocket to user {user_id}: {e}")
    
    @staticmethod
    def send_new_message(user_id, message_data):
        """
        Send new message notification via WebSocket.
        
        Args:
            user_id: ID of the user to notify
            message_data: Dictionary containing message data
        """
        try:
            channel_layer = get_channel_layer()
            
            async_to_sync(channel_layer.group_send)(
                f'notifications_user_{user_id}_messages',
                {
                    'type': 'new_message',
                    'timestamp': timezone.now().isoformat(),
                    **message_data
                }
            )
            
            logger.debug(f"New message notification sent via WebSocket to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending new message via WebSocket to user {user_id}: {e}")
    
    @staticmethod
    def send_payment_update(user_id, payment_data):
        """
        Send payment update notification via WebSocket.
        
        Args:
            user_id: ID of the user to notify
            payment_data: Dictionary containing payment data
        """
        try:
            channel_layer = get_channel_layer()
            
            async_to_sync(channel_layer.group_send)(
                f'notifications_user_{user_id}_payments',
                {
                    'type': 'payment_update',
                    'timestamp': timezone.now().isoformat(),
                    **payment_data
                }
            )
            
            logger.debug(f"Payment update sent via WebSocket to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending payment update via WebSocket to user {user_id}: {e}")
    
    @staticmethod
    def send_system_alert(user_ids, alert_data):
        """
        Send system alert to multiple users via WebSocket.
        
        Args:
            user_ids: List of user IDs to notify
            alert_data: Dictionary containing alert data
        """
        try:
            channel_layer = get_channel_layer()
            
            for user_id in user_ids:
                async_to_sync(channel_layer.group_send)(
                    f'notifications_user_{user_id}_system',
                    {
                        'type': 'system_alert',
                        'timestamp': timezone.now().isoformat(),
                        **alert_data
                    }
                )
            
            logger.debug(f"System alert sent via WebSocket to {len(user_ids)} users")
            
        except Exception as e:
            logger.error(f"Error sending system alert via WebSocket: {e}")
    
    @staticmethod
    def broadcast_system_alert(alert_data):
        """
        Broadcast system alert to all connected users.
        
        Args:
            alert_data: Dictionary containing alert data
        """
        try:
            channel_layer = get_channel_layer()
            
            async_to_sync(channel_layer.group_send)(
                'notifications_system_alerts',
                {
                    'type': 'system_alert',
                    'timestamp': timezone.now().isoformat(),
                    **alert_data
                }
            )
            
            logger.debug("System alert broadcasted to all connected users")
            
        except Exception as e:
            logger.error(f"Error broadcasting system alert via WebSocket: {e}")
    
    @staticmethod
    def update_unread_count(user_id, count):
        """
        Update unread count for a user.
        
        Args:
            user_id: ID of the user
            count: New unread count
        """
        try:
            channel_layer = get_channel_layer()
            
            async_to_sync(channel_layer.group_send)(
                f'notifications_user_{user_id}',
                {
                    'type': 'notification_read',
                    'notification_id': None,  # Indicates bulk update
                    'unread_count': count,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            logger.debug(f"Unread count updated via WebSocket for user {user_id}: {count}")
            
        except Exception as e:
            logger.error(f"Error updating unread count via WebSocket for user {user_id}: {e}")