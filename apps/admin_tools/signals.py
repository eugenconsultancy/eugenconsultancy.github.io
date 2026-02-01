# admin_tools/signals.py
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache

from apps.orders.models import Order
from apps.accounts.models import WriterProfile
from apps.payments.models import Payment
from .models import (
    AdminAuditLog, AdminTask, SystemConfiguration,
    SystemHealthCheck, AdminNotificationPreference
)
from .services import AdminAuditService

User = get_user_model()


# ===== USER SIGNALS =====

@receiver(post_save, sender=User)
def log_user_creation_update(sender, instance, created, **kwargs):
    """Log user creation and updates by admin users"""
    # Skip if no request context (e.g., during migrations, tests)
    from django.contrib.admin.models import LogEntry
    from django.contrib.contenttypes.models import ContentType
    
    if not hasattr(instance, '_request_user'):
        return
    
    admin_user = instance._request_user
    
    if admin_user and admin_user.is_staff:
        action_type = 'user_created' if created else 'user_updated'
        
        AdminAuditService.log_action(
            admin_user=admin_user,
            action_type=action_type,
            target_user=instance,
            description=f"{'Created' if created else 'Updated'} user: {instance.username} ({instance.email})",
            metadata={
                'user_id': instance.id,
                'username': instance.username,
                'email': instance.email,
                'is_active': instance.is_active,
                'is_staff': instance.is_staff,
                'is_superuser': instance.is_superuser
            }
        )


@receiver(post_delete, sender=User)
def log_user_deletion(sender, instance, **kwargs):
    """Log user deletion by admin users"""
    if hasattr(instance, '_request_user'):
        admin_user = instance._request_user
        
        if admin_user and admin_user.is_staff:
            AdminAuditService.log_action(
                admin_user=admin_user,
                action_type='user_deleted',
                target_user=None,  # User no longer exists
                description=f"Deleted user: {instance.username} ({instance.email})",
                metadata={
                    'user_id': instance.id,
                    'username': instance.username,
                    'email': instance.email
                }
            )


# ===== WRITER PROFILE SIGNALS =====

@receiver(post_save, sender=WriterProfile)
def log_writer_profile_changes(sender, instance, created, **kwargs):
    """Log writer profile changes by admin users"""
    if hasattr(instance, '_request_user'):
        admin_user = instance._request_user
        
        if admin_user and admin_user.is_staff:
            action_type = 'writer_created' if created else 'writer_updated'
            
            AdminAuditService.log_action(
                admin_user=admin_user,
                action_type=action_type,
                target_user=instance.user,
                description=f"{'Created' if created else 'Updated'} writer profile for: {instance.user.username}",
                metadata={
                    'writer_id': instance.id,
                    'verification_status': instance.verification_status,
                    'is_approved': instance.is_approved,
                    'rating': float(instance.rating) if instance.rating else None
                }
            )


@receiver(pre_save, sender=WriterProfile)
def detect_writer_profile_changes(sender, instance, **kwargs):
    """Detect and log specific field changes in writer profiles"""
    if not instance.pk or not hasattr(instance, '_request_user'):
        return
    
    try:
        old_instance = WriterProfile.objects.get(pk=instance.pk)
        admin_user = instance._request_user
        
        if admin_user and admin_user.is_staff:
            changes = {}
            
            # Check for important field changes
            fields_to_check = [
                'verification_status', 'is_approved', 'is_active',
                'hourly_rate', 'max_workload'
            ]
            
            for field in fields_to_check:
                old_value = getattr(old_instance, field)
                new_value = getattr(instance, field)
                
                if old_value != new_value:
                    changes[field] = {
                        'old': str(old_value),
                        'new': str(new_value)
                    }
            
            if changes:
                AdminAuditService.log_action(
                    admin_user=admin_user,
                    action_type='writer_updated',
                    target_user=instance.user,
                    description=f"Updated writer profile: {instance.user.username}",
                    metadata={
                        'writer_id': instance.id,
                        'changes': changes
                    }
                )
    
    except WriterProfile.DoesNotExist:
        pass


# ===== ORDER SIGNALS =====

@receiver(post_save, sender=Order)
def log_order_changes_by_admin(sender, instance, created, **kwargs):
    """Log order changes made by admin users"""
    if hasattr(instance, '_request_user'):
        admin_user = instance._request_user
        
        if admin_user and admin_user.is_staff:
            action_type = 'order_created' if created else 'order_updated'
            
            # Get writer info if assigned
            writer_info = None
            if instance.writer:
                writer_info = {
                    'id': instance.writer.id,
                    'username': instance.writer.user.username
                }
            
            AdminAuditService.log_action(
                admin_user=admin_user,
                action_type=action_type,
                target_user=instance.client,
                description=f"{'Created' if created else 'Updated'} order: {instance.order_number}",
                metadata={
                    'order_id': instance.id,
                    'order_number': instance.order_number,
                    'status': instance.status,
                    'writer': writer_info,
                    'subject': instance.subject,
                    'academic_level': instance.academic_level,
                    'deadline': instance.deadline.isoformat() if instance.deadline else None
                }
            )


@receiver(pre_save, sender=Order)
def detect_order_status_changes(sender, instance, **kwargs):
    """Detect and log order status changes"""
    if not instance.pk or not hasattr(instance, '_request_user'):
        return
    
    try:
        old_instance = Order.objects.get(pk=instance.pk)
        admin_user = instance._request_user
        
        if admin_user and admin_user.is_staff:
            # Check if status changed
            if old_instance.status != instance.status:
                AdminAuditService.log_action(
                    admin_user=admin_user,
                    action_type='order_updated',
                    target_user=instance.client,
                    description=f"Changed order status: {instance.order_number}",
                    metadata={
                        'order_id': instance.id,
                        'order_number': instance.order_number,
                        'status_change': {
                            'old': old_instance.status,
                            'new': instance.status
                        },
                        'timestamp': timezone.now().isoformat()
                    }
                )
            
            # Check if writer assignment changed
            if old_instance.writer != instance.writer:
                old_writer = None
                new_writer = None
                
                if old_instance.writer:
                    old_writer = {
                        'id': old_instance.writer.id,
                        'username': old_instance.writer.user.username
                    }
                
                if instance.writer:
                    new_writer = {
                        'id': instance.writer.id,
                        'username': instance.writer.user.username
                    }
                
                AdminAuditService.log_action(
                    admin_user=admin_user,
                    action_type='order_updated',
                    target_user=instance.client,
                    description=f"Changed writer assignment: {instance.order_number}",
                    metadata={
                        'order_id': instance.id,
                        'order_number': instance.order_number,
                        'writer_change': {
                            'old': old_writer,
                            'new': new_writer
                        }
                    }
                )
    
    except Order.DoesNotExist:
        pass


# ===== PAYMENT SIGNALS =====

@receiver(post_save, sender=Payment)
def log_payment_actions(sender, instance, created, **kwargs):
    """Log payment-related actions by admin users"""
    if hasattr(instance, '_request_user'):
        admin_user = instance._request_user
        
        if admin_user and admin_user.is_staff:
            action_type = 'payment_created' if created else 'payment_updated'
            
            AdminAuditService.log_action(
                admin_user=admin_user,
                action_type=action_type,
                target_user=instance.user,
                description=f"{'Created' if created else 'Updated'} payment: {instance.transaction_id}",
                metadata={
                    'payment_id': instance.id,
                    'transaction_id': instance.transaction_id,
                    'amount': float(instance.amount),
                    'currency': instance.currency,
                    'status': instance.status,
                    'payment_method': instance.payment_method,
                    'order_id': instance.order.id if instance.order else None,
                    'order_number': instance.order.order_number if instance.order else None
                }
            )


@receiver(pre_save, sender=Payment)
def detect_payment_status_changes(sender, instance, **kwargs):
    """Detect and log payment status changes"""
    if not instance.pk or not hasattr(instance, '_request_user'):
        return
    
    try:
        old_instance = Payment.objects.get(pk=instance.pk)
        admin_user = instance._request_user
        
        if admin_user and admin_user.is_staff:
            # Check if payment status changed
            if old_instance.status != instance.status:
                AdminAuditService.log_action(
                    admin_user=admin_user,
                    action_type='payment_updated',
                    target_user=instance.user,
                    description=f"Changed payment status: {instance.transaction_id}",
                    metadata={
                        'payment_id': instance.id,
                        'transaction_id': instance.transaction_id,
                        'status_change': {
                            'old': old_instance.status,
                            'new': instance.status
                        },
                        'amount': float(instance.amount),
                        'order_id': instance.order.id if instance.order else None
                    }
                )
    
    except Payment.DoesNotExist:
        pass


# ===== ADMIN TASK SIGNALS =====

@receiver(post_save, sender=AdminTask)
def handle_task_creation_update(sender, instance, created, **kwargs):
    """Handle task creation and updates"""
    if created:
        # Clear task-related cache on new task creation
        cache_keys = [
            'admin_dashboard_stats',
            f'user_tasks_{instance.assigned_to.id}' if instance.assigned_to else None,
            'overdue_tasks_count'
        ]
        
        for key in cache_keys:
            if key:
                cache.delete(key)
        
        # Send notification for new task assignment
        if instance.assigned_to:
            from .services import AdminTaskService
            AdminTaskService._send_task_assignment_notification(
                task=instance,
                assignee=instance.assigned_to,
                assigned_by=instance.created_by
            )
    
    else:
        # Clear cache on task update
        cache.delete(f'user_tasks_{instance.assigned_to.id}' if instance.assigned_to else None)
        cache.delete('overdue_tasks_count')


@receiver(post_delete, sender=AdminTask)
def handle_task_deletion(sender, instance, **kwargs):
    """Handle task deletion - clear cache"""
    cache.delete(f'user_tasks_{instance.assigned_to.id}' if instance.assigned_to else None)
    cache.delete('overdue_tasks_count')
    cache.delete('admin_dashboard_stats')


# ===== SYSTEM CONFIGURATION SIGNALS =====

@receiver(pre_save, sender=SystemConfiguration)
def log_configuration_changes(sender, instance, **kwargs):
    """Log system configuration changes"""
    if not instance.pk:
        return
    
    try:
        old_instance = SystemConfiguration.objects.get(pk=instance.pk)
        
        # Check if value changed
        if old_instance.value != instance.value:
            # Try to get admin user from request
            admin_user = None
            import inspect
            for frame_info in inspect.stack():
                frame = frame_info.frame
                request = frame.f_locals.get('request')
                if request and hasattr(request, 'user'):
                    if request.user.is_staff:
                        admin_user = request.user
                        break
            
            if admin_user:
                AdminAuditService.log_action(
                    admin_user=admin_user,
                    action_type='config_updated',
                    metadata={
                        'config_key': instance.key,
                        'category': instance.category,
                        'old_value': old_instance.value,
                        'new_value': instance.value,
                        'description': instance.description
                    }
                )
    
    except SystemConfiguration.DoesNotExist:
        pass


@receiver(post_save, sender=SystemConfiguration)
def clear_config_cache_on_save(sender, instance, **kwargs):
    """Clear cache when configuration is saved"""
    cache_key = f'system_config_{instance.key}'
    cache.delete(cache_key)
    
    # Also clear category cache
    category_cache_key = f'system_configs_category_{instance.category}'
    cache.delete(category_cache_key)


@receiver(post_delete, sender=SystemConfiguration)
def clear_config_cache_on_delete(sender, instance, **kwargs):
    """Clear cache when configuration is deleted"""
    cache_key = f'system_config_{instance.key}'
    cache.delete(cache_key)
    
    category_cache_key = f'system_configs_category_{instance.category}'
    cache.delete(category_cache_key)


# ===== SYSTEM HEALTH CHECK SIGNALS =====

@receiver(post_save, sender=SystemHealthCheck)
def handle_health_check_results(sender, instance, created, **kwargs):
    """Handle system health check results"""
    if created:
        # Clear health check cache
        cache.delete('latest_health_check')
        cache.delete('health_check_stats')
        
        # Send alerts for critical issues
        if instance.status == 'critical' and len(instance.issues) > 0:
            from .services import SystemHealthService
            SystemHealthService._send_health_alert(instance)


# ===== NOTIFICATION PREFERENCE SIGNALS =====

@receiver(post_save, sender=User)
def create_notification_preferences(sender, instance, created, **kwargs):
    """Create default notification preferences for new staff users"""
    if created and instance.is_staff:
        AdminNotificationPreference.objects.get_or_create(
            user=instance,
            defaults={
                'email_task_assignments': True,
                'email_task_updates': True,
                'email_system_alerts': True,
                'email_audit_alerts': False,
                'email_health_checks': False,
                'in_app_task_notifications': True,
                'in_app_system_notifications': True
            }
        )


# ===== CUSTOM SIGNAL HANDLERS =====

def log_custom_admin_action(action_type, admin_user, target_user=None, 
                           description=None, metadata=None, request=None):
    """
    Custom signal-like function to log admin actions from anywhere in the code
    
    Usage:
        from apps.admin_tools.signals import log_custom_admin_action
        log_custom_admin_action(
            action_type='custom_action',
            admin_user=request.user,
            target_user=some_user,
            description='Performed custom action',
            metadata={'key': 'value'}
        )
    """
    AdminAuditService.log_action(
        admin_user=admin_user,
        action_type=action_type,
        target_user=target_user,
        description=description,
        metadata=metadata,
        request=request
    )


# ===== REQUEST/RESPONSE SIGNAL HANDLERS =====

def admin_action_middleware(get_response):
    """
    Middleware to attach request user to model instances for signal logging
    
    Add this to your MIDDLEWARE in settings.py:
        'admin_tools.signals.admin_action_middleware',
    """
    def middleware(request):
        # Attach request user to request for signals to access
        request._admin_user = request.user if request.user.is_staff else None
        
        response = get_response(request)
        return response
    
    return middleware


# ===== CONTEXT PROCESSOR =====

def admin_context_processor(request):
    """
    Context processor to add admin tools context to templates
    
    Add to TEMPLATES context_processors in settings.py:
        'admin_tools.signals.admin_context_processor',
    """
    context = {}
    
    if request.user.is_authenticated and request.user.is_staff:
        # Add admin-specific context
        from .services import AdminTaskService
        
        context['admin_pending_tasks'] = AdminTaskService.get_user_tasks(
            request.user, 
            status=['pending', 'in_progress'],
            limit=5
        )
        context['admin_overdue_tasks'] = AdminTaskService.get_overdue_tasks().count()
        
        # Add notification preferences
        try:
            context['admin_notification_prefs'] = AdminNotificationPreference.objects.get(
                user=request.user
            )
        except AdminNotificationPreference.DoesNotExist:
            context['admin_notification_prefs'] = None
    
    return context