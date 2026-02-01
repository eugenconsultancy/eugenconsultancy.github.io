# apps/messaging/views.py
import logging
from django.shortcuts import get_object_or_404
from django.db import models
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from apps.messaging.models import Conversation, Message, MessageAttachment
from apps.messaging.services import (
    ConversationService, 
    MessageAttachmentService,
    MessageSecurityService
)
from apps.orders.models import Order
from apps.messaging.serializers import (
    ConversationSerializer,
    MessageSerializer,
    SendMessageSerializer,
    AttachmentSerializer
)

logger = logging.getLogger(__name__)


class ConversationListView(generics.ListAPIView):
    """
    List all conversations for the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationSerializer
    
    def get_queryset(self):
        # Get conversations where user is either client or writer
        user_orders = Order.objects.filter(
            models.Q(client=self.request.user) | 
            models.Q(assigned_writer=self.request.user)
        )
        
        return Conversation.objects.filter(
            order__in=user_orders
        ).select_related(
            'order',
            'order__client',
            'order__assigned_writer'
        ).prefetch_related(
            'messages'
        ).order_by('-updated_at')


class ConversationDetailView(generics.RetrieveAPIView):
    """
    Retrieve a specific conversation with its messages.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConversationSerializer
    
    def get_object(self):
        conversation_id = self.kwargs.get('conversation_id')
        conversation = get_object_or_404(
            Conversation.objects.select_related(
                'order',
                'order__client',
                'order__assigned_writer'
            ),
            id=conversation_id
        )
        
        # Check authorization
        if (self.request.user not in conversation.participants and 
            not self.request.user.is_staff):
            self.permission_denied(
                self.request, 
                message="You are not authorized to view this conversation"
            )
        
        return conversation


class MessageListView(generics.ListAPIView):
    """
    List messages for a specific conversation.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MessageSerializer
    
    def get_queryset(self):
        conversation_id = self.kwargs.get('conversation_id')
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        # Check authorization
        if (self.request.user not in conversation.participants and 
            not self.request.user.is_staff):
            self.permission_denied(
                self.request,
                message="You are not authorized to view these messages"
            )
        
        # Get messages
        messages = ConversationService.get_conversation_messages(
            conversation=conversation,
            user=self.request.user,
            limit=100
        )
        
        # Mark messages as read
        unread_messages = messages.filter(is_read=False).exclude(sender=self.request.user)
        for message in unread_messages:
            ConversationService.mark_message_as_read(message, self.request.user)
        
        return messages
    
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        
        # Add conversation info to response
        conversation_id = self.kwargs.get('conversation_id')
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        response.data['conversation'] = {
            'id': str(conversation.id),
            'order_id': conversation.order.order_id,
            'order_title': conversation.order.title,
            'is_closed': conversation.is_closed,
            'participants': [
                {
                    'id': str(user.id),
                    'email': user.email,
                    'full_name': user.get_full_name(),
                    'role': 'writer' if hasattr(user, 'writer_profile') else 'client'
                }
                for user in conversation.participants
            ]
        }
        
        return response


class SendMessageView(generics.CreateAPIView):
    """
    Send a new message in a conversation.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SendMessageSerializer
    parser_classes = [MultiPartParser, FormParser]
    
    def perform_create(self, serializer):
        conversation_id = self.kwargs.get('conversation_id')
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        # Check authorization
        if self.request.user not in conversation.participants:
            self.permission_denied(
                self.request,
                message="You are not a participant in this conversation"
            )
        
        # Check if conversation is closed
        if conversation.is_closed:
            self.permission_denied(
                self.request,
                message="Cannot send message to closed conversation"
            )
        
        # Get validated data
        validated_data = serializer.validated_data
        content = validated_data.get('content')
        attachments = self.request.FILES.getlist('attachments')
        
        # Send message
        message = ConversationService.send_message(
            conversation=conversation,
            sender=self.request.user,
            content=content,
            attachments=attachments
        )
        
        # Return the created message
        serializer.instance = message
        
        # Log the action
        logger.info(f"Message sent by {self.request.user.email} in conversation {conversation.id}")


class DownloadAttachmentView(generics.RetrieveAPIView):
    """
    Download a message attachment.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        attachment_id = self.kwargs.get('attachment_id')
        
        try:
            # Get attachment with authorization check
            attachment = MessageAttachmentService.get_attachment(
                attachment_id=attachment_id,
                user=request.user
            )
            
            # Log download
            logger.info(f"Attachment downloaded: {attachment.original_filename} by {request.user.email}")
            
            # Return file response
            response = Response(status=status.HTTP_200_OK)
            response['Content-Disposition'] = f'attachment; filename="{attachment.original_filename}"'
            response['Content-Type'] = attachment.file_type
            
            # Serve file
            attachment.file.open('rb')
            response.data = attachment.file.read()
            attachment.file.close()
            
            return response
            
        except PermissionError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error downloading attachment {attachment_id}: {e}")
            return Response(
                {'error': 'Failed to download attachment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MarkMessageReadView(APIView):
    """
    Mark a specific message as read.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, message_id):
        try:
            message = get_object_or_404(
                Message.objects.select_related('conversation'),
                id=message_id
            )
            
            # Check authorization
            if request.user not in message.conversation.participants:
                return Response(
                    {'error': 'Not authorized to mark this message as read'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Mark as read
            ConversationService.mark_message_as_read(message, request.user)
            
            return Response(
                {'status': 'Message marked as read'},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error marking message {message_id} as read: {e}")
            return Response(
                {'error': 'Failed to mark message as read'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ConversationStatsView(APIView):
    """
    Get statistics for a conversation.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, conversation_id):
        try:
            conversation = get_object_or_404(Conversation, id=conversation_id)
            
            # Check authorization
            if (request.user not in conversation.participants and 
                not request.user.is_staff):
                return Response(
                    {'error': 'Not authorized to view conversation stats'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            from apps.messaging.services import ConversationAnalyticsService
            stats = ConversationAnalyticsService.get_conversation_stats(conversation)
            
            return Response(stats, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting conversation stats {conversation_id}: {e}")
            return Response(
                {'error': 'Failed to get conversation statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CloseConversationView(APIView):
    """
    Close a conversation (admin only).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def post(self, request, conversation_id):
        try:
            conversation = get_object_or_404(Conversation, id=conversation_id)
            
            # Check if already closed
            if conversation.is_closed:
                return Response(
                    {'error': 'Conversation is already closed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Close conversation
            conversation.close()
            
            # Send system message
            from apps.messaging.services import ConversationService
            ConversationService.send_system_message(
                conversation=conversation,
                content="This conversation has been closed by an administrator."
            )
            
            logger.info(f"Conversation {conversation_id} closed by {request.user.email}")
            
            return Response(
                {'status': 'Conversation closed successfully'},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error closing conversation {conversation_id}: {e}")
            return Response(
                {'error': 'Failed to close conversation'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminConversationListView(generics.ListAPIView):
    """
    List all conversations (admin only).
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = ConversationSerializer
    
    def get_queryset(self):
        queryset = Conversation.objects.all().select_related(
            'order',
            'order__client',
            'order__assigned_writer'
        ).order_by('-updated_at')
        
        # Apply filters
        status_filter = self.request.query_params.get('status')
        if status_filter == 'open':
            queryset = queryset.filter(is_closed=False)
        elif status_filter == 'closed':
            queryset = queryset.filter(is_closed=True)
        
        order_id = self.request.query_params.get('order_id')
        if order_id:
            queryset = queryset.filter(order__order_id__icontains=order_id)
        
        user_email = self.request.query_params.get('user_email')
        if user_email:
            queryset = queryset.filter(
                models.Q(order__client__email__icontains=user_email) |
                models.Q(order__assigned_writer__email__icontains=user_email)
            )
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        
        # Add summary statistics
        total = Conversation.objects.count()
        open_count = Conversation.objects.filter(is_closed=False).count()
        closed_count = Conversation.objects.filter(is_closed=True).count()
        
        response.data['summary'] = {
            'total_conversations': total,
            'open_conversations': open_count,
            'closed_conversations': closed_count
        }
        
        return response