"""
Admin tools services for managing admin tasks, audits, and system configuration.
"""
import json
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q, Avg, Sum
from django.contrib.auth import get_user_model
from django.core.cache import cache
# apps/admin_tools/services.py

from django.db import models

from .models import AdminAuditLog, AdminTask, SystemConfiguration, SystemHealthCheck

User = get_user_model()


class AdminAuditService:
    """Service for logging and managing admin audit trails"""
    
    @staticmethod
    def log_admin_action(
        admin_user,
        action_type: str,
        action_description: str,
        target_user=None,
        target_order=None,
        target_payment=None,
        previous_state: Dict = None,
        new_state: Dict = None,
        changes_summary: str = '',
        request=None
    ) -> AdminAuditLog:
        """
        Log an admin action for audit trail
        
        Args:
            admin_user: Admin user performing the action
            action_type: Type of action (from AdminAuditLog.ActionType)
            action_description: Description of the action
            target_user: Target user (if applicable)
            target_order: Target order (if applicable)
            target_payment: Target payment (if applicable)
            previous_state: Previous state before action
            new_state: New state after action
            changes_summary: Summary of changes
            request: HTTP request object (for IP and user agent)
        
        Returns:
            AdminAuditLog object
        """
        # Get IP and user agent from request
        ip_address = None
        user_agent = ''
        
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Create audit log entry
        audit_log = AdminAuditLog.objects.create(
            admin_user=admin_user,
            action_type=action_type,
            action_description=action_description,
            target_user=target_user,
            target_order=target_order,
            target_payment=target_payment,
            previous_state=previous_state or {},
            new_state=new_state or {},
            changes_summary=changes_summary,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        return audit_log
    
    @staticmethod
    def get_admin_activity_summary(days: int = 30) -> Dict:
        """
        Get summary of admin activity for the past N days
        
        Args:
            days: Number of days to look back
        
        Returns:
            Dictionary with activity summary
        """
        start_date = timezone.now() - timezone.timedelta(days=days)
        
        # Get activity by type
        activity_by_type = AdminAuditLog.objects.filter(
            created_at__gte=start_date
        ).values('action_type').annotate(
            count=Count('id'),
            last_action=models.Max('created_at')
        ).order_by('-count')
        
        # Get top admins
        top_admins = AdminAuditLog.objects.filter(
            created_at__gte=start_date
        ).values('admin_user__email', 'admin_user__first_name', 'admin_user__last_name').annotate(
            action_count=Count('id')
        ).order_by('-action_count')[:10]
        
        # Get recent actions
        recent_actions = AdminAuditLog.objects.filter(
            created_at__gte=start_date
        ).select_related('admin_user', 'target_user', 'target_order').order_by('-created_at')[:20]
        
        return {
            'period_days': days,
            'start_date': start_date,
            'total_actions': AdminAuditLog.objects.filter(created_at__gte=start_date).count(),
            'activity_by_type': list(activity_by_type),
            'top_admins': list(top_admins),
            'recent_actions': list(recent_actions.values(
                'id', 'action_type', 'action_description',
                'admin_user__email', 'target_user__email',
                'created_at'
            )),
        }
    
    @staticmethod
    def export_audit_logs(format: str = 'json', filters: Dict = None) -> str:
        """
        Export audit logs in specified format
        
        Args:
            format: Export format (json, csv)
            filters: Optional filters for the logs
        
        Returns:
            Exported data as string
        """
        queryset = AdminAuditLog.objects.all()
        
        # Apply filters
        if filters:
            if filters.get('action_type'):
                queryset = queryset.filter(action_type=filters['action_type'])
            if filters.get('admin_user'):
                queryset = queryset.filter(admin_user_id=filters['admin_user'])
            if filters.get('start_date'):
                queryset = queryset.filter(created_at__gte=filters['start_date'])
            if filters.get('end_date'):
                queryset = queryset.filter(created_at__lte=filters['end_date'])
        
        # Select related fields
        queryset = queryset.select_related(
            'admin_user',
            'target_user',
            'target_order',
            'target_payment'
        )
        
        if format == 'json':
            import json
            data = list(queryset.values(
                'id', 'action_type', 'action_description',
                'admin_user__email', 'admin_user__first_name', 'admin_user__last_name',
                'target_user__email', 'target_user__first_name', 'target_user__last_name',
                'target_order__id', 'target_payment__id',
                'previous_state', 'new_state', 'changes_summary',
                'ip_address', 'user_agent', 'created_at'
            ))
            return json.dumps(data, indent=2, default=str)
        
        elif format == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'ID', 'Action Type', 'Description', 'Admin Email',
                'Target Email', 'Order ID', 'Payment ID',
                'Changes Summary', 'IP Address', 'Timestamp'
            ])
            
            # Write data
            for log in queryset:
                writer.writerow([
                    str(log.id),
                    log.get_action_type_display(),
                    log.action_description[:100],
                    log.admin_user.email if log.admin_user else '',
                    log.target_user.email if log.target_user else '',
                    str(log.target_order.id) if log.target_order else '',
                    str(log.target_payment.id) if log.target_payment else '',
                    log.changes_summary[:100],
                    log.ip_address or '',
                    log.created_at.isoformat()
                ])
            
            return output.getvalue()
        
        else:
            raise ValueError(f"Unsupported format: {format}")


class AdminTaskService:
    """Service for managing admin tasks"""
    
    @staticmethod
    def create_task(
        title: str,
        description: str,
        task_type: str,
        created_by,
        priority: str = 'medium',
        assigned_to=None,
        target_user=None,
        target_order=None,
        due_date=None,
        estimated_hours=None
    ) -> AdminTask:
        """
        Create a new admin task
        
        Args:
            title: Task title
            description: Task description
            task_type: Type of task (from AdminTask.TaskType)
            created_by: User creating the task
            priority: Task priority (low, medium, high, urgent)
            assigned_to: User assigned to the task
            target_user: Target user (if applicable)
            target_order: Target order (if applicable)
            due_date: Due date for the task
            estimated_hours: Estimated hours to complete
        
        Returns:
            AdminTask object
        """
        task = AdminTask.objects.create(
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            created_by=created_by,
            assigned_to=assigned_to,
            target_user=target_user,
            target_order=target_order,
            due_date=due_date,
            estimated_hours=estimated_hours
        )
        
        return task
    
    @staticmethod
    def assign_task(task_id, assigned_to, assigned_by) -> Tuple[bool, str]:
        """
        Assign a task to an admin user
        
        Args:
            task_id: Task ID
            assigned_to: User to assign to
            assigned_by: User making the assignment
        
        Returns:
            Tuple of (success, message)
        """
        try:
            task = AdminTask.objects.get(id=task_id)
            
            # Check if user is staff
            if not assigned_to.is_staff:
                return False, "Can only assign tasks to staff members"
            
            # Update task
            task.assigned_to = assigned_to
            task.status = AdminTask.TaskStatus.IN_PROGRESS
            task.save()
            
            # Log the assignment
            AdminAuditService.log_admin_action(
                admin_user=assigned_by,
                action_type=AdminAuditLog.ActionType.ORDER_ASSIGNMENT,
                action_description=f"Assigned task '{task.title}' to {assigned_to.email}",
                target_user=assigned_to,
                previous_state={'assigned_to': None},
                new_state={'assigned_to': assigned_to.email}
            )
            
            return True, "Task assigned successfully"
        
        except AdminTask.DoesNotExist:
            return False, "Task not found"
    
    @staticmethod
    def complete_task(task_id, result_text: str = "", completed_by=None) -> Tuple[bool, str]:
        """
        Mark a task as completed
        
        Args:
            task_id: Task ID
            result_text: Result/notes for completion
            completed_by: User marking as completed
        
        Returns:
            Tuple of (success, message)
        """
        try:
            task = AdminTask.objects.get(id=task_id)
            
            # Calculate actual hours if not set
            if not task.actual_hours and task.created_at:
                hours = (timezone.now() - task.created_at).total_seconds() / 3600
                task.actual_hours = round(hours, 2)
            
            # Mark as completed
            task.status = AdminTask.TaskStatus.COMPLETED
            task.completed_at = timezone.now()
            task.result = result_text
            task.save()
            
            # Log completion
            if completed_by:
                AdminAuditService.log_admin_action(
                    admin_user=completed_by,
                    action_type=AdminAuditLog.ActionType.SYSTEM_CONFIG_CHANGE,
                    action_description=f"Completed task '{task.title}'",
                    target_user=task.target_user,
                    target_order=task.target_order,
                    previous_state={'status': task.get_status_display()},
                    new_state={'status': 'Completed'}
                )
            
            return True, "Task marked as completed"
        
        except AdminTask.DoesNotExist:
            return False, "Task not found"
    
    @staticmethod
    def get_task_statistics(days: int = 30) -> Dict:
        """
        Get statistics for admin tasks
        
        Args:
            days: Number of days to look back
        
        Returns:
            Dictionary with task statistics
        """
        start_date = timezone.now() - timezone.timedelta(days=days)
        
        # Overall statistics
        total_tasks = AdminTask.objects.filter(created_at__gte=start_date).count()
        completed_tasks = AdminTask.objects.filter(
            created_at__gte=start_date,
            status=AdminTask.TaskStatus.COMPLETED
        ).count()
        
        # Task type distribution
        tasks_by_type = AdminTask.objects.filter(
            created_at__gte=start_date
        ).values('task_type').annotate(
            count=Count('id'),
            completed=Count('id', filter=Q(status=AdminTask.TaskStatus.COMPLETED)),
            in_progress=Count('id', filter=Q(status=AdminTask.TaskStatus.IN_PROGRESS)),
            pending=Count('id', filter=Q(status=AdminTask.TaskStatus.PENDING))
        ).order_by('-count')
        
        # Admin performance
        admin_performance = AdminTask.objects.filter(
            created_at__gte=start_date,
            assigned_to__isnull=False
        ).values(
            'assigned_to__email',
            'assigned_to__first_name',
            'assigned_to__last_name'
        ).annotate(
            total_assigned=Count('id'),
            completed=Count('id', filter=Q(status=AdminTask.TaskStatus.COMPLETED)),
            avg_completion_hours=Avg('actual_hours'),
            overdue=Count('id', filter=Q(due_date__lt=timezone.now()) & ~Q(status__in=[
                AdminTask.TaskStatus.COMPLETED, AdminTask.TaskStatus.CANCELLED
            ]))
        ).order_by('-total_assigned')
        
        # Overdue tasks
        overdue_tasks = AdminTask.objects.filter(
            due_date__lt=timezone.now(),
            status__in=[AdminTask.TaskStatus.PENDING, AdminTask.TaskStatus.IN_PROGRESS]
        ).count()
        
        # Average completion time
        avg_completion_hours = AdminTask.objects.filter(
            status=AdminTask.TaskStatus.COMPLETED,
            actual_hours__isnull=False
        ).aggregate(
            avg_hours=Avg('actual_hours')
        )['avg_hours'] or 0
        
        return {
            'period_days': days,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            'overdue_tasks': overdue_tasks,
            'avg_completion_hours': round(avg_completion_hours, 2),
            'tasks_by_type': list(tasks_by_type),
            'admin_performance': list(admin_performance),
        }


class SystemConfigService:
    """Service for managing system configuration"""
    
    @staticmethod
    def get_config(key: str, default=None):
        """
        Get a configuration value by key
        
        Args:
            key: Configuration key
            default: Default value if not found
        
        Returns:
            Configuration value
        """
        cache_key = f"system_config_{key}"
        value = cache.get(cache_key)
        
        if value is None:
            try:
                config = SystemConfiguration.objects.get(key=key)
                value = config.value
                cache.set(cache_key, value, 300)  # Cache for 5 minutes
            except SystemConfiguration.DoesNotExist:
                value = default
        
        return value
    
    @staticmethod
    def set_config(key: str, value, user=None, description: str = "") -> Tuple[bool, str]:
        """
        Set a configuration value
        
        Args:
            key: Configuration key
            value: Value to set
            user: User making the change
            description: Description of the change
        
        Returns:
            Tuple of (success, message)
        """
        try:
            with transaction.atomic():
                config, created = SystemConfiguration.objects.get_or_create(
                    key=key,
                    defaults={
                        'category': 'platform',
                        'display_name': key.replace('_', ' ').title(),
                        'is_editable': True,
                        'modified_by': user,
                    }
                )
                
                # Store previous value for audit
                previous_value = config.value
                
                # Update value based on type
                if isinstance(value, str):
                    config.value_string = value
                    config.value_number = None
                    config.value_boolean = None
                    config.value_json = None
                elif isinstance(value, (int, float)):
                    config.value_number = value
                    config.value_string = ''
                    config.value_boolean = None
                    config.value_json = None
                elif isinstance(value, bool):
                    config.value_boolean = value
                    config.value_string = ''
                    config.value_number = None
                    config.value_json = None
                elif isinstance(value, (dict, list)):
                    config.value_json = value
                    config.value_string = ''
                    config.value_number = None
                    config.value_boolean = None
                else:
                    config.value_string = str(value)
                    config.value_number = None
                    config.value_boolean = None
                    config.value_json = None
                
                config.modified_by = user
                config.save()
                
                # Clear cache
                cache_key = f"system_config_{key}"
                cache.delete(cache_key)
                
                # Log the change
                if user:
                    AdminAuditService.log_admin_action(
                        admin_user=user,
                        action_type=AdminAuditLog.ActionType.SYSTEM_CONFIG_CHANGE,
                        action_description=f"Updated configuration: {key}",
                        previous_state={key: previous_value},
                        new_state={key: value},
                        changes_summary=description or f"Updated {key} from {previous_value} to {value}"
                    )
                
                action = "created" if created else "updated"
                return True, f"Configuration {key} {action} successfully"
        
        except Exception as e:
            return False, f"Error updating configuration: {str(e)}"
    
    @staticmethod
    def get_all_configs(category: str = None) -> Dict:
        """
        Get all configuration values
        
        Args:
            category: Optional category filter
        
        Returns:
            Dictionary of configuration values
        """
        cache_key = f"system_configs_all_{category or 'all'}"
        configs = cache.get(cache_key)
        
        if configs is None:
            queryset = SystemConfiguration.objects.all()
            if category:
                queryset = queryset.filter(category=category)
            
            configs = {}
            for config in queryset:
                configs[config.key] = {
                    'value': config.value,
                    'category': config.category,
                    'display_name': config.display_name,
                    'description': config.description,
                    'is_editable': config.is_editable,
                    'requires_restart': config.requires_restart,
                }
            
            cache.set(cache_key, configs, 300)  # Cache for 5 minutes
        
        return configs
    
    @staticmethod
    def initialize_default_configs() -> Dict:
        """
        Initialize default system configurations
        
        Returns:
            Dictionary of initialized configurations
        """
        default_configs = {
            # Platform settings
            'platform_name': {'value': 'EBWriting', 'category': 'platform'},
            'platform_fee_percentage': {'value': 20.0, 'category': 'platform'},
            'minimum_order_amount': {'value': 10.0, 'category': 'order'},
            'maximum_order_amount': {'value': 10000.0, 'category': 'order'},
            
            # Writer settings
            'writer_approval_required': {'value': True, 'category': 'writer'},
            'writer_minimum_rating': {'value': 4.0, 'category': 'writer'},
            'writer_max_concurrent_orders': {'value': 5, 'category': 'writer'},
            
            # Order settings
            'order_expiry_hours': {'value': 72, 'category': 'order'},
            'order_revision_period': {'value': 7, 'category': 'order'},
            'max_revisions_per_order': {'value': 3, 'category': 'order'},
            
            # Payment settings
            'minimum_payout_amount': {'value': 50.0, 'category': 'payment'},
            'escrow_hold_period': {'value': 7, 'category': 'payment'},
            
            # Notification settings
            'email_notifications_enabled': {'value': True, 'category': 'notification'},
            'push_notifications_enabled': {'value': True, 'category': 'notification'},
            
            # Security settings
            'session_timeout_minutes': {'value': 120, 'category': 'security'},
            'max_login_attempts': {'value': 5, 'category': 'security'},
            'password_min_length': {'value': 12, 'category': 'security'},
            
            # Compliance settings
            'data_retention_days': {'value': 365, 'category': 'compliance'},
            'gdpr_compliance_enabled': {'value': True, 'category': 'compliance'},
        }
        
        initialized = {}
        for key, config_data in default_configs.items():
            if not SystemConfiguration.objects.filter(key=key).exists():
                SystemConfiguration.objects.create(
                    key=key,
                    category=config_data['category'],
                    value_string=config_data['value'] if isinstance(config_data['value'], str) else '',
                    value_number=config_data['value'] if isinstance(config_data['value'], (int, float)) else None,
                    value_boolean=config_data['value'] if isinstance(config_data['value'], bool) else None,
                    display_name=key.replace('_', ' ').title(),
                    description=f"Default configuration for {key}",
                    is_editable=True,
                )
                initialized[key] = config_data['value']
        
        return initialized


class SystemHealthService:
    """Service for system health monitoring"""
    
    @staticmethod
    def perform_health_check() -> SystemHealthCheck:
        """
        Perform a comprehensive system health check
        
        Returns:
            SystemHealthCheck object
        """
        from django.db import connection, DatabaseError
        from django.core.cache import cache
        from django.core.mail import send_mail
        import psutil
        import os
        
        issues = []
        recommendations = []
        
        # Database check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_response_time = 10  # Placeholder - should measure actual time
                database_status = SystemHealthCheck.HealthStatus.HEALTHY
        except DatabaseError:
            db_response_time = 0
            database_status = SystemHealthCheck.HealthStatus.CRITICAL
            issues.append("Database connection failed")
            recommendations.append("Check database service and connection settings")
        
        # Cache check
        try:
            start_time = timezone.now()
            cache.set('health_check', 'test', 10)
            cache.get('health_check')
            cache_response_time = (timezone.now() - start_time).total_seconds() * 1000
            cache_status = SystemHealthCheck.HealthStatus.HEALTHY
        except Exception:
            cache_response_time = 0
            cache_status = SystemHealthCheck.HealthStatus.CRITICAL
            issues.append("Cache service failed")
            recommendations.append("Check Redis/cache service")
        
        # Celery check (simplified)
        try:
            from django_celery_results.models import TaskResult
            recent_tasks = TaskResult.objects.filter(
                date_done__gte=timezone.now() - timezone.timedelta(minutes=5)
            ).count()
            celery_status = SystemHealthCheck.HealthStatus.HEALTHY if recent_tasks > 0 else SystemHealthCheck.HealthStatus.WARNING
        except:
            celery_status = SystemHealthCheck.HealthStatus.WARNING
            issues.append("Celery task monitoring unavailable")
        
        # Email check
        try:
            # Just check if email backend is configured
            from django.conf import settings
            email_backend = getattr(settings, 'EMAIL_BACKEND', '')
            if email_backend and 'dummy' not in email_backend:
                email_status = SystemHealthCheck.HealthStatus.HEALTHY
            else:
                email_status = SystemHealthCheck.HealthStatus.WARNING
                issues.append("Email backend is dummy or not configured")
        except:
            email_status = SystemHealthCheck.HealthStatus.WARNING
        
        # Storage check
        try:
            from django.core.files.storage import default_storage
            test_file = default_storage.save('health_check.txt', b'test')
            default_storage.delete(test_file)
            storage_status = SystemHealthCheck.HealthStatus.HEALTHY
        except Exception as e:
            storage_status = SystemHealthCheck.HealthStatus.CRITICAL
            issues.append(f"Storage service failed: {str(e)}")
            recommendations.append("Check storage configuration and permissions")
        
        # API check (simplified)
        api_status = SystemHealthCheck.HealthStatus.HEALTHY
        
        # System metrics
        server_load = psutil.cpu_percent(interval=1)
        memory_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        
        # Active counts (simplified)
        active_users = User.objects.filter(
            last_login__gte=timezone.now() - timezone.timedelta(hours=1)
        ).count()
        
        try:
            from apps.orders.models import Order
            active_orders = Order.objects.filter(
                status__in=['assigned', 'in_progress']
            ).count()
        except:
            active_orders = 0
        
        pending_tasks = AdminTask.objects.filter(
            status__in=['pending', 'in_progress']
        ).count()
        
        queue_size = 0  # Placeholder for actual queue monitoring
        
        # Calculate overall status
        critical_count = sum([
            1 for status in [database_status, cache_status, storage_status] 
            if status == SystemHealthCheck.HealthStatus.CRITICAL
        ])
        warning_count = sum([
            1 for status in [database_status, cache_status, celery_status, email_status, storage_status, api_status]
            if status == SystemHealthCheck.HealthStatus.WARNING
        ])
        
        if critical_count > 0:
            overall_status = SystemHealthCheck.HealthStatus.CRITICAL
        elif warning_count > 0:
            overall_status = SystemHealthCheck.HealthStatus.WARNING
        else:
            overall_status = SystemHealthCheck.HealthStatus.HEALTHY
        
        # Calculate score (0-100)
        component_score = 100 - (critical_count * 40) - (warning_count * 20)
        metrics_score = 100 - max(0, (server_load - 80) * 0.5) - max(0, (memory_usage - 85) * 0.5) - max(0, (disk_usage - 90) * 1)
        score = min(100, max(0, (component_score * 0.6) + (metrics_score * 0.4)))
        
        # Create health check record
        health_check = SystemHealthCheck.objects.create(
            database_status=database_status,
            cache_status=cache_status,
            celery_status=celery_status,
            email_status=email_status,
            storage_status=storage_status,
            api_status=api_status,
            database_response_time=db_response_time,
            cache_response_time=cache_response_time,
            server_load=server_load,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            active_users=active_users,
            active_orders=active_orders,
            pending_tasks=pending_tasks,
            queue_size=queue_size,
            issues_found=issues,
            recommendations=recommendations,
            overall_status=overall_status,
            score=score
        )
        
        return health_check
    
    @staticmethod
    def get_health_trend(days: int = 7) -> Dict:
        """
        Get health check trend over time
        
        Args:
            days: Number of days to look back
        
        Returns:
            Dictionary with health trend data
        """
        start_date = timezone.now() - timezone.timedelta(days=days)
        
        health_checks = SystemHealthCheck.objects.filter(
            created_at__gte=start_date
        ).order_by('created_at')
        
        # Prepare trend data
        trend_data = {
            'timestamps': [],
            'scores': [],
            'status_counts': {
                'healthy': [],
                'warning': [],
                'critical': []
            }
        }
        
        for check in health_checks:
            trend_data['timestamps'].append(check.created_at.isoformat())
            trend_data['scores'].append(float(check.score))
            trend_data['status_counts']['healthy'].append(
                1 if check.overall_status == SystemHealthCheck.HealthStatus.HEALTHY else 0
            )
            trend_data['status_counts']['warning'].append(
                1 if check.overall_status == SystemHealthCheck.HealthStatus.WARNING else 0
            )
            trend_data['status_counts']['critical'].append(
                1 if check.overall_status == SystemHealthCheck.HealthStatus.CRITICAL else 0
            )
        
        # Get current issues
        latest_check = health_checks.last()
        current_issues = latest_check.issues_found if latest_check else []
        
        # Calculate statistics
        avg_score = sum(trend_data['scores']) / len(trend_data['scores']) if trend_data['scores'] else 0
        uptime_percentage = (sum(trend_data['status_counts']['healthy']) / len(trend_data['status_counts']['healthy']) * 100) if trend_data['status_counts']['healthy'] else 0
        
        return {
            'period_days': days,
            'avg_score': round(avg_score, 2),
            'uptime_percentage': round(uptime_percentage, 2),
            'current_issues': current_issues,
            'trend_data': trend_data,
            'latest_check': {
                'timestamp': latest_check.created_at.isoformat() if latest_check else None,
                'status': latest_check.get_overall_status_display() if latest_check else 'Unknown',
                'score': float(latest_check.score) if latest_check else 0
            } if latest_check else None
        }