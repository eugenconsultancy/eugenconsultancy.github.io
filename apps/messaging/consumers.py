# apps/messaging/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async

from apps.messaging.models import Conversation, Message

logger = logging.getLogger(__name__)
User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time messaging."""
    
    async def connect(self):
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        
        # Check if user has access to conversation
        has_access = await self.check_conversation_access()
        if not has_access:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(f"User {self.user.email} connected to conversation {self.conversation_id}")
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        logger.info(f"User {self.user.email} disconnected from conversation {self.conversation_id}")
    
    async def receive(self, text_data):
        """Receive message from WebSocket."""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', 'chat_message')
            
            if message_type == 'chat_message':
                content = text_data_json.get('content', '').strip()
                
                if not content:
                    return
                
                # Create message in database
                message = await self.create_message(content)
                
                # Send message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message_id': str(message.id),
                        'sender_id': str(self.user.id),
                        'sender_email': self.user.email,
                        'sender_name': self.user.get_full_name() or self.user.email,
                        'content': content,
                        'timestamp': message.created_at.isoformat(),
                        'is_system_message': False
                    }
                )
            
            elif message_type == 'typing':
                # Send typing indicator
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'typing_indicator',
                        'user_id': str(self.user.id),
                        'user_name': self.user.get_full_name() or self.user.email,
                        'is_typing': text_data_json.get('is_typing', False)
                    }
                )
            
            elif message_type == 'read_receipt':
                # Mark message as read
                message_id = text_data_json.get('message_id')
                if message_id:
                    await self.mark_message_as_read(message_id)
                    
                    # Send read receipt to room group
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'read_receipt',
                            'message_id': message_id,
                            'user_id': str(self.user.id),
                            'user_name': self.user.get_full_name() or self.user.email,
                            'read_at': text_data_json.get('read_at')
                        }
                    )
        
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    async def chat_message(self, event):
        """Receive chat message from room group."""
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message_id': event['message_id'],
            'sender_id': event['sender_id'],
            'sender_email': event['sender_email'],
            'sender_name': event['sender_name'],
            'content': event['content'],
            'timestamp': event['timestamp'],
            'is_system_message': event['is_system_message']
        }))
    
    async def typing_indicator(self, event):
        """Receive typing indicator from room group."""
        # Don't send typing indicator to the user who's typing
        if str(self.user.id) != event['user_id']:
            await self.send(text_data=json.dumps({
                'type': 'typing_indicator',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'is_typing': event['is_typing']
            }))
    
    async def read_receipt(self, event):
        """Receive read receipt from room group."""
        # Don't send read receipt to the user who read the message
        if str(self.user.id) != event['user_id']:
            await self.send(text_data=json.dumps({
                'type': 'read_receipt',
                'message_id': event['message_id'],
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'read_at': event['read_at']
            }))
    
    async def system_message(self, event):
        """Receive system message from room group."""
        await self.send(text_data=json.dumps({
            'type': 'system_message',
            'content': event['content'],
            'timestamp': event['timestamp']
        }))
    
    @database_sync_to_async
    def check_conversation_access(self):
        """Check if user has access to conversation."""
        try:
            conversation = Conversation.objects.get(id=self.conversation_id)
            return self.user in conversation.participants or self.user.is_staff
        except Conversation.DoesNotExist:
            return False
    
    @database_sync_to_async
    def create_message(self, content):
        """Create message in database."""
        conversation = Conversation.objects.get(id=self.conversation_id)
        
        message = Message.objects.create(
            conversation=conversation,
            sender=self.user,
            content=content,
            is_system_message=False
        )
        
        # Update conversation timestamp
        conversation.save(update_fields=['updated_at'])
        
        return message
    
    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        """Mark message as read."""
        try:
            message = Message.objects.get(id=message_id)
            if message.sender != self.user:  # Don't mark own messages as read
                message.mark_as_read(self.user)
                return True
        except Message.DoesNotExist:
            pass
        return False


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time notifications."""
    
    async def connect(self):
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.room_group_name = f'notifications_{self.user.id}'
        
        # Join user's personal notification group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        logger.info(f"User {self.user.email} connected to notifications")
    
    async def disconnect(self, close_code):
        # Leave notification group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        logger.info(f"User {self.user.email} disconnected from notifications")
    
    async def receive(self, text_data):
        """Receive message from WebSocket."""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'subscribe':
                # Subscribe to specific notification types
                notification_types = text_data_json.get('types', [])
                for ntype in notification_types:
                    group_name = f'notifications_{self.user.id}_{ntype}'
                    await self.channel_layer.group_add(
                        group_name,
                        self.channel_name
                    )
            
            elif message_type == 'unsubscribe':
                # Unsubscribe from specific notification types
                notification_types = text_data_json.get('types', [])
                for ntype in notification_types:
                    group_name = f'notifications_{self.user.id}_{ntype}'
                    await self.channel_layer.group_discard(
                        group_name,
                        self.channel_name
                    )
        
        except json.JSONDecodeError:
            logger.error("Invalid JSON received in notification consumer")
        except Exception as e:
            logger.error(f"Error processing notification WebSocket message: {e}")
    
    async def notification_message(self, event):
        """Send notification to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'id': event.get('id'),
            'title': event.get('title'),
            'message': event.get('message'),
            'notification_type': event.get('notification_type'),
            'priority': event.get('priority'),
            'action_url': event.get('action_url'),
            'action_text': event.get('action_text'),
            'timestamp': event.get('timestamp'),
            'unread_count': event.get('unread_count', 0)
        }))