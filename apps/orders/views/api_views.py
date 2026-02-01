"""
API views for orders (AJAX endpoints).
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q
import json

from apps.orders.models import Order
from apps.orders.services import AssignmentService


class OrderStatusAPIView(LoginRequiredMixin, View):
    """API endpoint to get order status."""
    
    def get(self, request, pk, *args, **kwargs):
        """Get order status information."""
        order = get_object_or_404(Order, pk=pk)
        
        # Check permission
        if not (request.user.is_staff or 
                order.client == request.user or 
                order.writer == request.user):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Prepare response data
        data = {
            'order_number': order.order_number,
            'state': order.state,
            'state_display': order.get_state_display(),
            'progress_percentage': order.progress_percentage,
            'is_overdue': order.is_overdue,
            'time_remaining': {
                'days': order.time_remaining.days,
                'hours': order.time_remaining.seconds // 3600,
                'minutes': (order.time_remaining.seconds % 3600) // 60,
                'total_seconds': order.time_remaining.total_seconds(),
            },
            'deadline': order.deadline.isoformat() if order.deadline else None,
            'revision_count': order.revision_count,
            'max_revisions': order.max_revisions,
            'can_request_revision': order.can_request_revision,
            'can_be_assigned': order.can_be_assigned,
            'timestamp': timezone.now().isoformat(),
        }
        
        return JsonResponse(data)


class TimeRemainingAPIView(LoginRequiredMixin, View):
    """API endpoint to get time remaining for order."""
    
    def get(self, request, pk, *args, **kwargs):
        """Get time remaining for order."""
        order = get_object_or_404(Order, pk=pk)
        
        # Check permission
        if not (request.user.is_staff or 
                order.client == request.user or 
                order.writer == request.user):
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        time_remaining = order.time_remaining
        
        data = {
            'order_id': order.id,
            'order_number': order.order_number,
            'is_overdue': order.is_overdue,
            'time_remaining': {
                'days': time_remaining.days,
                'hours': time_remaining.seconds // 3600,
                'minutes': (time_remaining.seconds % 3600) // 60,
                'seconds': time_remaining.seconds,
                'total_seconds': time_remaining.total_seconds(),
            },
            'human_readable': str(time_remaining),
            'deadline': order.deadline.isoformat() if order.deadline else None,
            'timestamp': timezone.now().isoformat(),
        }
        
        return JsonResponse(data)


class AvailableWritersAPIView(LoginRequiredMixin, View):
    """API endpoint to get available writers for an order."""
    
    def get(self, request, pk, *args, **kwargs):
        """Get available writers for an order."""
        if not request.user.is_staff:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        order = get_object_or_404(Order, pk=pk)
        
        # Check if order can be assigned
        if not order.can_be_assigned:
            return JsonResponse({
                'error': 'Order cannot be assigned in current state',
                'can_be_assigned': False
            })
        
        # Get available writers using assignment service
        result = AssignmentService.get_available_writers_for_order(order.id)
        
        if 'error' in result:
            return JsonResponse(result, status=400)
        
        # Prepare response data
        writers_data = []
        for writer_info in result['writers']:
            writer = writer_info['writer']
            writers_data.append({
                'id': writer.id,
                'email': writer.email,
                'full_name': writer.get_full_name(),
                'specialization': writer.writer_profile.specialization,
                'education_level': writer.writer_profile.get_education_level_display(),
                'average_rating': float(writer.writer_profile.average_rating),
                'success_rate': float(writer.writer_profile.success_rate),
                'current_orders': writer.writer_profile.current_orders,
                'max_orders': writer.writer_profile.max_orders,
                'is_available': writer.writer_profile.is_available,
                'match_score': writer_info['score'],
                'match_reasons': writer_info['match_reasons'],
            })
        
        data = {
            'order_id': order.id,
            'order_number': order.order_number,
            'order_title': order.title,
            'order_subject': order.subject,
            'order_academic_level': order.get_academic_level_display(),
            'total_available_writers': result['total_available'],
            'writers': writers_data,
            'timestamp': timezone.now().isoformat(),
        }
        
        return JsonResponse(data)