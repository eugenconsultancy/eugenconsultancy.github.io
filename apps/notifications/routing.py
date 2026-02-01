# apps/notifications/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    
    Handles:
    - Live notification delivery
    - Notification status updates
    - User preference changes
    - Unread count updates
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope['user']
        
        # Reject unauthenticated connections
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return
        
        # Create user-specific room name
        self.user_room = f'notifications_user_{self.user.id}'
        
        # Create notification type rooms
        self.order_room = f'notifications_user_{self.user.id}_order_updates'
        self.message_room = f'notifications_user_{self.user.id}_messages'
        self.system_room = f'notifications_user_{self.user.id}_system'
        self.payment_room = f'notifications_user_{self.user.id}_payments'
        
        # Join all notification rooms for this user
        await self.channel_layer.group_add(
            self.user_room,
            self.channel_name
        )
        
        # Join specific notification type rooms based on user preferences
        from apps.notifications.models import NotificationPreference
        
        try:
            pref = await database_sync_to_async(NotificationPreference.objects.get)(
                user=self.user
            )
            
            if pref.push_enabled:
                # Join order updates room if enabled
                if pref.is_category_enabled('order_updates', 'push'):
                    await self.channel_layer.group_add(
                        self.order_room,
                        self.channel_name
                    )
                
                # Join message notifications room if enabled
                if pref.is_category_enabled('messages', 'push'):
                    await self.channel_layer.group_add(
                        self.message_room,
                        self.channel_name
                    )
                
                # Join system notifications room if enabled
                if pref.is_category_enabled('system', 'push'):
                    await self.channel_layer.group_add(
                        self.system_room,
                        self.channel_name
                    )
                
                # Join payment notifications room if enabled
                if pref.is_category_enabled('payments', 'push'):
                    await self.channel_layer.group_add(
                        self.payment_room,
                        self.channel_name
                    )
        
        except NotificationPreference.DoesNotExist:
            # If no preferences exist, join all rooms
            await self.channel_layer.group_add(
                self.order_room,
                self.channel_name
            )
            await self.channel_layer.group_add(
                self.message_room,
                self.channel_name
            )
            await self.channel_layer.group_add(
                self.system_room,
                self.channel_name
            )
            await self.channel_layer.group_add(
                self.payment_room,
                self.channel_name
            )
        
        await self.accept()
        
        # Send initial unread count
        unread_count = await self.get_unread_count()
        await self.send_initial_data(unread_count)
        
        logger.info(f"Notification WebSocket connected for user: {self.user.email}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave all rooms
        await self.channel_layer.group_discard(
            self.user_room,
            self.channel_name
        )
        await self.channel_layer.group_discard(
            self.order_room,
            self.channel_name
        )
        await self.channel_layer.group_discard(
            self.message_room,
            self.channel_name
        )
        await self.channel_layer.group_discard(
            self.system_room,
            self.channel_name
        )
        await self.channel_layer.group_discard(
            self.payment_room,
            self.channel_name
        )
        
        logger.info(f"Notification WebSocket disconnected for user: {self.user.email}")
    
    async def receive(self, text_data):
        """Receive message from WebSocket."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'mark_read':
                # Mark notification as read
                notification_id = data.get('notification_id')
                if notification_id:
                    await self.mark_notification_as_read(notification_id)
                    
                    # Update unread count for user
                    unread_count = await self.get_unread_count()
                    await self.send_unread_count(unread_count)
            
            elif message_type == 'mark_all_read':
                # Mark all notifications as read
                await self.mark_all_notifications_as_read()
                
                # Update unread count
                await self.send_unread_count(0)
            
            elif message_type == 'update_preferences':
                # Update notification preferences
                preferences = data.get('preferences', {})
                await self.update_notification_preferences(preferences)
                
                # Re-subscribe to rooms based on new preferences
                await self.update_room_subscriptions(preferences)
                
                await self.send(text_data=json.dumps({
                    'type': 'preferences_updated',
                    'success': True,
                    'timestamp': timezone.now().isoformat()
                }))
            
            elif message_type == 'ping':
                # Respond to ping with pong
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': timezone.now().isoformat()
                }))
            
            elif message_type == 'subscribe':
                # Subscribe to specific notification types
                categories = data.get('categories', [])
                await self.subscribe_to_categories(categories)
            
            elif message_type == 'unsubscribe':
                # Unsubscribe from specific notification types
                categories = data.get('categories', [])
                await self.unsubscribe_from_categories(categories)
            
            elif message_type == 'get_unread_count':
                # Get current unread count
                unread_count = await self.get_unread_count()
                await self.send_unread_count(unread_count)
            
            else:
                logger.warning(f"Unknown message type: {message_type}")
        
        except json.JSONDecodeError:
            logger.error("Invalid JSON received in notification consumer")
        except Exception as e:
            logger.error(f"Error processing notification WebSocket message: {e}")
    
    async def send_initial_data(self, unread_count):
        """Send initial data to client on connection."""
        await self.send(text_data=json.dumps({
            'type': 'initial_data',
            'unread_count': unread_count,
            'user_id': str(self.user.id),
            'timestamp': timezone.now().isoformat()
        }))
    
    async def send_unread_count(self, count):
        """Send unread count update to client."""
        await self.send(text_data=json.dumps({
            'type': 'unread_count_update',
            'count': count,
            'timestamp': timezone.now().isoformat()
        }))
    
    async def send_notification(self, event):
        """
        Send notification to WebSocket client.
        Called when a notification is sent to the group.
        """
        # Check if user has push notifications enabled for this category
        if await self.should_send_notification(event.get('category')):
            await self.send(text_data=json.dumps({
                'type': 'notification',
                'id': event.get('id'),
                'title': event.get('title'),
                'message': event.get('message'),
                'category': event.get('category'),
                'notification_type': event.get('notification_type'),
                'priority': event.get('priority'),
                'action_url': event.get('action_url'),
                'action_text': event.get('action_text'),
                'context_data': event.get('context_data', {}),
                'timestamp': event.get('timestamp'),
                'unread_count': event.get('unread_count', 0)
            }))
    
    async def notification_created(self, event):
        """Handle notification_created event from system."""
        # Forward to send_notification method
        await self.send_notification(event)
    
    async def notification_read(self, event):
        """Handle notification_read event."""
        await self.send(text_data=json.dumps({
            'type': 'notification_read',
            'notification_id': event.get('notification_id'),
            'read_at': event.get('read_at'),
            'unread_count': event.get('unread_count', 0)
        }))
    
    async def system_alert(self, event):
        """Handle system-wide alerts."""
        await self.send(text_data=json.dumps({
            'type': 'system_alert',
            'title': event.get('title'),
            'message': event.get('message'),
            'alert_type': event.get('alert_type'),
            'timestamp': event.get('timestamp')
        }))
    
    async def order_update(self, event):
        """Handle order update notifications."""
        if await self.should_send_notification('order_updates'):
            await self.send(text_data=json.dumps({
                'type': 'order_update',
                'order_id': event.get('order_id'),
                'order_title': event.get('order_title'),
                'status': event.get('status'),
                'old_status': event.get('old_status'),
                'message': event.get('message'),
                'timestamp': event.get('timestamp'),
                'action_url': event.get('action_url')
            }))
    
    async def new_message(self, event):
        """Handle new message notifications."""
        if await self.should_send_notification('messages'):
            await self.send(text_data=json.dumps({
                'type': 'new_message',
                'message_id': event.get('message_id'),
                'conversation_id': event.get('conversation_id'),
                'order_id': event.get('order_id'),
                'sender_id': event.get('sender_id'),
                'sender_name': event.get('sender_name'),
                'preview': event.get('preview'),
                'timestamp': event.get('timestamp'),
                'action_url': event.get('action_url')
            }))
    
    async def payment_update(self, event):
        """Handle payment update notifications."""
        if await self.should_send_notification('payments'):
            await self.send(text_data=json.dumps({
                'type': 'payment_update',
                'payment_id': event.get('payment_id'),
                'order_id': event.get('order_id'),
                'status': event.get('status'),
                'amount': event.get('amount'),
                'currency': event.get('currency'),
                'message': event.get('message'),
                'timestamp': event.get('timestamp'),
                'action_url': event.get('action_url')
            }))
    
    @database_sync_to_async
    def get_unread_count(self):
        """Get unread notification count for user."""
        from apps.notifications.models import Notification
        return Notification.objects.filter(
            user=self.user,
            is_read=False
        ).count()
    
    @database_sync_to_async
    def mark_notification_as_read(self, notification_id):
        """Mark a specific notification as read."""
        from apps.notifications.models import Notification
        try:
            notification = Notification.objects.get(
                id=notification_id,
                user=self.user
            )
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False
    
    @database_sync_to_async
    def mark_all_notifications_as_read(self):
        """Mark all notifications as read for user."""
        from apps.notifications.models import Notification
        from django.utils import timezone
        
        updated = Notification.objects.filter(
            user=self.user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        return updated
    
    @database_sync_to_async
    def update_notification_preferences(self, preferences):
        """Update user's notification preferences."""
        from apps.notifications.models import NotificationPreference
        
        pref, created = NotificationPreference.objects.get_or_create(
            user=self.user
        )
        
        if 'email_enabled' in preferences:
            pref.email_enabled = preferences['email_enabled']
        
        if 'push_enabled' in preferences:
            pref.push_enabled = preferences['push_enabled']
        
        if 'sms_enabled' in preferences:
            pref.sms_enabled = preferences['sms_enabled']
        
        if 'quiet_hours_enabled' in preferences:
            pref.quiet_hours_enabled = preferences['quiet_hours_enabled']
        
        if 'quiet_hours_start' in preferences:
            pref.quiet_hours_start = preferences['quiet_hours_start']
        
        if 'quiet_hours_end' in preferences:
            pref.quiet_hours_end = preferences['quiet_hours_end']
        
        if 'preferences' in preferences:
            # Merge existing preferences with new ones
            existing_prefs = pref.preferences
            existing_prefs.update(preferences['preferences'])
            pref.preferences = existing_prefs
        
        pref.save()
        return True
    
    async def update_room_subscriptions(self, preferences):
        """Update WebSocket room subscriptions based on preferences."""
        push_enabled = preferences.get('push_enabled', True)
        
        if not push_enabled:
            # Leave all notification rooms if push disabled
            await self.channel_layer.group_discard(
                self.order_room,
                self.channel_name
            )
            await self.channel_layer.group_discard(
                self.message_room,
                self.channel_name
            )
            await self.channel_layer.group_discard(
                self.system_room,
                self.channel_name
            )
            await self.channel_layer.group_discard(
                self.payment_room,
                self.channel_name
            )
        else:
            # Update room subscriptions based on category preferences
            category_prefs = preferences.get('preferences', {})
            
            # Order updates
            if category_prefs.get('order_updates', {}).get('push', True):
                await self.channel_layer.group_add(
                    self.order_room,
                    self.channel_name
                )
            else:
                await self.channel_layer.group_discard(
                    self.order_room,
                    self.channel_name
                )
            
            # Messages
            if category_prefs.get('messages', {}).get('push', True):
                await self.channel_layer.group_add(
                    self.message_room,
                    self.channel_name
                )
            else:
                await self.channel_layer.group_discard(
                    self.message_room,
                    self.channel_name
                )
            
            # System
            if category_prefs.get('system', {}).get('push', True):
                await self.channel_layer.group_add(
                    self.system_room,
                    self.channel_name
                )
            else:
                await self.channel_layer.group_discard(
                    self.system_room,
                    self.channel_name
                )
            
            # Payments
            if category_prefs.get('payments', {}).get('push', True):
                await self.channel_layer.group_add(
                    self.payment_room,
                    self.channel_name
                )
            else:
                await self.channel_layer.group_discard(
                    self.payment_room,
                    self.channel_name
                )
    
    async def subscribe_to_categories(self, categories):
        """Subscribe to specific notification categories."""
        for category in categories:
            room_name = f'notifications_user_{self.user.id}_{category}'
            await self.channel_layer.group_add(
                room_name,
                self.channel_name
            )
        
        await self.send(text_data=json.dumps({
            'type': 'subscribed',
            'categories': categories,
            'timestamp': timezone.now().isoformat()
        }))
    
    async def unsubscribe_from_categories(self, categories):
        """Unsubscribe from specific notification categories."""
        for category in categories:
            room_name = f'notifications_user_{self.user.id}_{category}'
            await self.channel_layer.group_discard(
                room_name,
                self.channel_name
            )
        
        await self.send(text_data=json.dumps({
            'type': 'unsubscribed',
            'categories': categories,
            'timestamp': timezone.now().isoformat()
        }))
    
    @database_sync_to_async
    def should_send_notification(self, category):
        """Check if notification should be sent based on user preferences."""
        from apps.notifications.models import NotificationPreference
        
        try:
            pref = NotificationPreference.objects.get(user=self.user)
            
            # Check if push notifications are enabled
            if not pref.push_enabled:
                return False
            
            # Check if category is enabled for push notifications
            return pref.is_category_enabled(category, 'push')
        
        except NotificationPreference.DoesNotExist:
            # Default to sending if no preferences exist
            return True