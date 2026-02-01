# apps/admin_tools/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q, Avg, Sum
from django.core.paginator import Paginator
from django.core.cache import cache
from django.urls import reverse_lazy
import json
import csv
from django.utils.encoding import smart_str

from apps.accounts.models import User, WriterProfile
from apps.orders.models import Order
from apps.payments.models import Payment
from .models import AdminAuditLog, AdminTask, SystemConfiguration, SystemHealthCheck, AdminNotificationPreference
from .forms import (
    AdminTaskForm, TaskAssignmentForm, TaskCompletionForm,
    SystemConfigurationForm, BulkConfigurationForm,
    AdminNotificationPreferenceForm, AuditLogFilterForm,
    HealthCheckFilterForm
)
from .services import (
    AdminAuditService, AdminTaskService, 
    SystemConfigService, SystemHealthService
)


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to ensure user is admin/staff"""
    
    def test_func(self):
        return self.request.user.is_staff
    
    def handle_no_permission(self):
        messages.error(self.request, "You don't have permission to access admin tools.")
        return redirect('dashboard')


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """Admin dashboard view"""
    
    template_name = 'admin_tools/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get dashboard statistics
        today = timezone.now().date()
        week_ago = today - timezone.timedelta(days=7)
        month_ago = today - timezone.timedelta(days=30)
        
        # Platform statistics
        context['total_users'] = User.objects.filter(is_active=True).count()
        context['total_writers'] = WriterProfile.objects.filter(is_approved=True).count()
        context['total_orders'] = Order.objects.count()
        context['active_orders'] = Order.objects.filter(
            status__in=['assigned', 'in_progress']
        ).count()
        
        # Recent activity
        context['recent_tasks'] = AdminTask.objects.filter(
            status__in=['pending', 'in_progress']
        ).order_by('-due_date', '-created_at')[:10]
        
        context['recent_audit_logs'] = AdminAuditLog.objects.select_related(
            'admin_user', 'target_user'
        ).order_by('-created_at')[:10]
        
        # Pending actions
        context['pending_writer_reviews'] = WriterProfile.objects.filter(
            verification_status='under_admin_review'
        ).count()
        
        context['pending_orders'] = Order.objects.filter(
            status='paid'
        ).count()
        
        # Task statistics
        context['my_pending_tasks'] = AdminTask.objects.filter(
            assigned_to=self.request.user,
            status__in=['pending', 'in_progress']
        ).count()
        
        context['overdue_tasks'] = AdminTask.objects.filter(
            due_date__lt=timezone.now(),
            status__in=['pending', 'in_progress']
        ).count()
        
        # System health
        try:
            context['latest_health_check'] = SystemHealthCheck.objects.latest('created_at')
        except SystemHealthCheck.DoesNotExist:
            context['latest_health_check'] = None
        
        return context


# ===== TASK MANAGEMENT VIEWS =====

class TaskListView(AdminRequiredMixin, ListView):
    """List all admin tasks"""
    
    model = AdminTask
    template_name = 'admin_tools/tasks/list.html'
    context_object_name = 'tasks'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'assigned_to', 'created_by', 'related_order'
        )
        
        # Apply filters
        status = self.request.GET.get('status')
        priority = self.request.GET.get('priority')
        assigned_to = self.request.GET.get('assigned_to')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        
        if priority and priority != 'all':
            queryset = queryset.filter(priority=priority)
        
        if assigned_to and assigned_to != 'all':
            if assigned_to == 'me':
                queryset = queryset.filter(assigned_to=self.request.user)
            else:
                queryset = queryset.filter(assigned_to__id=assigned_to)
        
        if date_from:
            queryset = queryset.filter(due_date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(due_date__lte=date_to)
        
        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(related_order__order_number__icontains=search)
            )
        
        return queryset.order_by('-priority', 'due_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter form
        context['filter_form'] = {
            'status': self.request.GET.get('status', 'all'),
            'priority': self.request.GET.get('priority', 'all'),
            'assigned_to': self.request.GET.get('assigned_to', 'all'),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
            'search': self.request.GET.get('search', ''),
        }
        
        # Add available assignees for filter dropdown
        context['admin_users'] = User.objects.filter(
            is_staff=True, is_active=True
        ).values('id', 'username', 'email')
        
        # Add statistics
        context['total_tasks'] = AdminTask.objects.count()
        context['pending_tasks'] = AdminTask.objects.filter(
            status__in=['pending', 'in_progress']
        ).count()
        context['overdue_tasks'] = AdminTask.objects.filter(
            due_date__lt=timezone.now(),
            status__in=['pending', 'in_progress']
        ).count()
        
        return context


class TaskDetailView(AdminRequiredMixin, DetailView):
    """View task details"""
    
    model = AdminTask
    template_name = 'admin_tools/tasks/detail.html'
    context_object_name = 'task'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.object
        
        # Add task change history
        context['audit_logs'] = AdminAuditLog.objects.filter(
            Q(admin_user=self.request.user) | Q(admin_user__isnull=True),
            action_type='task_update',
            metadata__contains={'task_id': str(task.id)}
        ).order_by('-created_at')[:10]
        
        # Add available actions based on task status and user
        context['available_actions'] = self.get_available_actions(task)
        
        return context
    
    def get_available_actions(self, task):
        actions = []
        user = self.request.user
        
        if task.status == 'pending' and (user == task.assigned_to or user.is_superuser):
            actions.append('start')
        
        if task.status == 'in_progress' and user == task.assigned_to:
            actions.append('complete')
            actions.append('pause')
        
        if task.status == 'paused' and user == task.assigned_to:
            actions.append('resume')
        
        if user.is_superuser or user == task.created_by:
            actions.append('reassign')
            actions.append('edit')
            actions.append('delete')
        
        return actions


class TaskCreateView(AdminRequiredMixin, CreateView):
    """Create a new admin task"""
    
    model = AdminTask
    form_class = AdminTaskForm
    template_name = 'admin_tools/tasks/create.html'
    success_url = reverse_lazy('admin_tools:tasks')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        
        # Set default priority if not provided
        if not form.instance.priority:
            form.instance.priority = 'medium'
        
        # Set due date to 3 days from now if not provided
        if not form.instance.due_date:
            form.instance.due_date = timezone.now() + timezone.timedelta(days=3)
        
        response = super().form_valid(form)
        
        # Log the task creation
        AdminAuditService.log_action(
            admin_user=self.request.user,
            action_type='task_created',
            target_user=form.instance.assigned_to,
            metadata={
                'task_id': form.instance.id,
                'title': form.instance.title,
                'priority': form.instance.priority,
            }
        )
        
        messages.success(self.request, f'Task "{form.instance.title}" created successfully.')
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Pre-fill form with order if order_id is provided
        order_id = self.request.GET.get('order_id')
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                context['related_order'] = order
            except Order.DoesNotExist:
                pass
        
        return context


class TaskUpdateView(AdminRequiredMixin, UpdateView):
    """Update an existing task"""
    
    model = AdminTask
    form_class = AdminTaskForm
    template_name = 'admin_tools/tasks/update.html'
    context_object_name = 'task'
    
    def get_success_url(self):
        return reverse_lazy('admin_tools:task_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        old_task = AdminTask.objects.get(pk=form.instance.pk)
        response = super().form_valid(form)
        
        # Log changes
        changes = {}
        for field in ['title', 'description', 'priority', 'due_date', 'status', 'assigned_to']:
            old_value = getattr(old_task, field)
            new_value = getattr(form.instance, field)
            
            if old_value != new_value:
                changes[field] = {
                    'old': str(old_value),
                    'new': str(new_value)
                }
        
        if changes:
            AdminAuditService.log_action(
                admin_user=self.request.user,
                action_type='task_updated',
                target_user=old_task.assigned_to,
                metadata={
                    'task_id': form.instance.id,
                    'changes': changes
                }
            )
        
        messages.success(self.request, f'Task "{form.instance.title}" updated successfully.')
        return response


class TaskDeleteView(AdminRequiredMixin, View):
    """Delete a task"""
    
    def post(self, request, pk):
        task = get_object_or_404(AdminTask, pk=pk)
        
        # Check permission
        if not (request.user.is_superuser or request.user == task.created_by):
            messages.error(request, "You don't have permission to delete this task.")
            return redirect('admin_tools:task_detail', pk=pk)
        
        task_title = task.title
        task.delete()
        
        AdminAuditService.log_action(
            admin_user=request.user,
            action_type='task_deleted',
            metadata={
                'task_title': task_title,
                'task_id': pk
            }
        )
        
        messages.success(request, f'Task "{task_title}" deleted successfully.')
        return redirect('admin_tools:tasks')


class TaskActionView(AdminRequiredMixin, View):
    """Handle task actions (start, complete, pause, resume)"""
    
    def post(self, request, pk, action):
        task = get_object_or_404(AdminTask, pk=pk)
        user = request.user
        
        # Validate action permission
        if not self.validate_action_permission(task, user, action):
            messages.error(request, "You don't have permission to perform this action.")
            return redirect('admin_tools:task_detail', pk=pk)
        
        # Perform action
        if action == 'start':
            return self.start_task(task, user)
        elif action == 'complete':
            return self.complete_task(task, user)
        elif action == 'pause':
            return self.pause_task(task, user)
        elif action == 'resume':
            return self.resume_task(task, user)
        else:
            messages.error(request, "Invalid action.")
            return redirect('admin_tools:task_detail', pk=pk)
    
    def validate_action_permission(self, task, user, action):
        if user.is_superuser:
            return True
        
        if action in ['start', 'complete', 'pause', 'resume']:
            return user == task.assigned_to
        
        return False
    
    def start_task(self, task, user):
        if task.status != 'pending':
            messages.error(user, "Task cannot be started from its current status.")
            return redirect('admin_tools:task_detail', pk=task.pk)
        
        task.status = 'in_progress'
        task.started_at = timezone.now()
        task.save()
        
        AdminAuditService.log_action(
            admin_user=user,
            action_type='task_started',
            target_user=task.assigned_to,
            metadata={'task_id': task.id}
        )
        
        messages.success(user, f'Task "{task.title}" started successfully.')
        return redirect('admin_tools:task_detail', pk=task.pk)
    
    def complete_task(self, task, user):
        if task.status != 'in_progress':
            messages.error(user, "Only tasks in progress can be completed.")
            return redirect('admin_tools:task_detail', pk=task.pk)
        
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()
        
        AdminAuditService.log_action(
            admin_user=user,
            action_type='task_completed',
            target_user=task.assigned_to,
            metadata={'task_id': task.id}
        )
        
        messages.success(user, f'Task "{task.title}" completed successfully.')
        return redirect('admin_tools:task_detail', pk=task.pk)
    
    def pause_task(self, task, user):
        if task.status != 'in_progress':
            messages.error(user, "Only tasks in progress can be paused.")
            return redirect('admin_tools:task_detail', pk=task.pk)
        
        task.status = 'paused'
        task.save()
        
        AdminAuditService.log_action(
            admin_user=user,
            action_type='task_paused',
            target_user=task.assigned_to,
            metadata={'task_id': task.id}
        )
        
        messages.success(user, f'Task "{task.title}" paused.')
        return redirect('admin_tools:task_detail', pk=task.pk)
    
    def resume_task(self, task, user):
        if task.status != 'paused':
            messages.error(user, "Only paused tasks can be resumed.")
            return redirect('admin_tools:task_detail', pk=task.pk)
        
        task.status = 'in_progress'
        task.save()
        
        AdminAuditService.log_action(
            admin_user=user,
            action_type='task_resumed',
            target_user=task.assigned_to,
            metadata={'task_id': task.id}
        )
        
        messages.success(user, f'Task "{task.title}" resumed.')
        return redirect('admin_tools:task_detail', pk=task.pk)


class TaskBulkActionView(AdminRequiredMixin, View):
    """Handle bulk actions on tasks"""
    
    def post(self, request):
        task_ids = request.POST.getlist('task_ids')
        action = request.POST.get('bulk_action')
        
        if not task_ids:
            messages.error(request, "No tasks selected.")
            return redirect('admin_tools:tasks')
        
        tasks = AdminTask.objects.filter(id__in=task_ids)
        
        if action == 'delete':
            return self.bulk_delete(request, tasks)
        elif action == 'reassign':
            return self.bulk_reassign(request, tasks)
        elif action == 'complete':
            return self.bulk_complete(request, tasks)
        else:
            messages.error(request, "Invalid bulk action.")
            return redirect('admin_tools:tasks')
    
    def bulk_delete(self, request, tasks):
        # Check permission for all tasks
        for task in tasks:
            if not (request.user.is_superuser or request.user == task.created_by):
                messages.error(request, f"You don't have permission to delete task: {task.title}")
                return redirect('admin_tools:tasks')
        
        count = tasks.count()
        tasks.delete()
        
        AdminAuditService.log_action(
            admin_user=request.user,
            action_type='bulk_tasks_deleted',
            metadata={'count': count}
        )
        
        messages.success(request, f"{count} tasks deleted successfully.")
        return redirect('admin_tools:tasks')
    
    def bulk_reassign(self, request, tasks):
        new_assignee_id = request.POST.get('new_assignee')
        
        if not new_assignee_id:
            messages.error(request, "Please select an assignee.")
            return redirect('admin_tools:tasks')
        
        try:
            new_assignee = User.objects.get(id=new_assignee_id, is_staff=True)
        except User.DoesNotExist:
            messages.error(request, "Invalid assignee selected.")
            return redirect('admin_tools:tasks')
        
        count = 0
        for task in tasks:
            old_assignee = task.assigned_to
            task.assigned_to = new_assignee
            task.save()
            count += 1
            
            AdminAuditService.log_action(
                admin_user=request.user,
                action_type='task_reassigned',
                target_user=old_assignee,
                metadata={
                    'task_id': task.id,
                    'old_assignee_id': old_assignee.id if old_assignee else None,
                    'new_assignee_id': new_assignee.id
                }
            )
        
        messages.success(request, f"{count} tasks reassigned to {new_assignee.username}.")
        return redirect('admin_tools:tasks')
    
    def bulk_complete(self, request, tasks):
        count = 0
        for task in tasks:
            if task.status == 'in_progress':
                task.status = 'completed'
                task.completed_at = timezone.now()
                task.save()
                count += 1
                
                AdminAuditService.log_action(
                    admin_user=request.user,
                    action_type='task_completed',
                    target_user=task.assigned_to,
                    metadata={'task_id': task.id}
                )
        
        messages.success(request, f"{count} tasks marked as completed.")
        return redirect('admin_tools:tasks')


# ===== AUDIT LOG VIEWS =====

class AuditLogListView(AdminRequiredMixin, ListView):
    """View audit logs"""
    
    model = AdminAuditLog
    template_name = 'admin_tools/audit/list.html'
    context_object_name = 'audit_logs'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'admin_user', 'target_user'
        )
        
        # Apply filters
        form = AuditLogFilterForm(self.request.GET)
        if form.is_valid():
            action_type = form.cleaned_data.get('action_type')
            admin_user = form.cleaned_data.get('admin_user')
            target_user = form.cleaned_data.get('target_user')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            search = form.cleaned_data.get('search')
            
            if action_type:
                queryset = queryset.filter(action_type=action_type)
            
            if admin_user:
                queryset = queryset.filter(admin_user=admin_user)
            
            if target_user:
                queryset = queryset.filter(target_user=target_user)
            
            if date_from:
                queryset = queryset.filter(created_at__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(created_at__lte=date_to)
            
            if search:
                queryset = queryset.filter(
                    Q(description__icontains=search) |
                    Q(metadata__icontains=search) |
                    Q(ip_address__icontains=search)
                )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = AuditLogFilterForm(self.request.GET)
        
        # Add action type choices
        context['action_types'] = AdminAuditLog.ACTION_CHOICES
        
        # Add statistics
        context['total_logs'] = AdminAuditLog.objects.count()
        context['today_logs'] = AdminAuditLog.objects.filter(
            created_at__date=timezone.now().date()
        ).count()
        
        return context


class AuditLogExportView(AdminRequiredMixin, View):
    """Export audit logs to CSV"""
    
    def get(self, request):
        # Apply same filters as list view
        queryset = AdminAuditLog.objects.all()
        
        # Apply filters from request
        action_type = request.GET.get('action_type')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Generate CSV
        import csv
        from django.utils.encoding import smart_str
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_logs_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Timestamp', 'Action Type', 'Admin User', 'Target User',
            'Description', 'IP Address', 'Metadata'
        ])
        
        for log in queryset.order_by('-created_at'):
            writer.writerow([
                smart_str(log.created_at),
                smart_str(log.get_action_type_display()),
                smart_str(log.admin_user.username if log.admin_user else 'System'),
                smart_str(log.target_user.username if log.target_user else 'N/A'),
                smart_str(log.description),
                smart_str(log.ip_address),
                smart_str(json.dumps(log.metadata) if log.metadata else '')
            ])
        
        # Log the export action
        AdminAuditService.log_action(
            admin_user=request.user,
            action_type='audit_logs_exported',
            metadata={'count': queryset.count()}
        )
        
        return response


# ===== SYSTEM CONFIGURATION VIEWS =====

class SystemConfigurationView(AdminRequiredMixin, TemplateView):
    """View and manage system configurations"""
    
    template_name = 'admin_tools/config/list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all configurations grouped by category
        configs = SystemConfiguration.objects.all().order_by('category', 'key')
        grouped_configs = {}
        
        for config in configs:
            if config.category not in grouped_configs:
                grouped_configs[config.category] = []
            grouped_configs[config.category].append(config)
        
        context['grouped_configs'] = grouped_configs
        context['config_form'] = SystemConfigurationForm()
        context['bulk_form'] = BulkConfigurationForm()
        
        # Get recently modified configs
        context['recently_modified'] = SystemConfiguration.objects.order_by('-updated_at')[:10]
        
        return context


class ConfigurationUpdateView(AdminRequiredMixin, View):
    """Update a system configuration"""
    
    def post(self, request, pk):
        config = get_object_or_404(SystemConfiguration, pk=pk)
        form = SystemConfigurationForm(request.POST, instance=config)
        
        if form.is_valid():
            old_value = config.value
            new_value = form.cleaned_data['value']
            
            config = form.save()
            
            # Clear cache for this configuration
            cache_key = f'system_config_{config.key}'
            cache.delete(cache_key)
            
            # Log the change
            AdminAuditService.log_action(
                admin_user=request.user,
                action_type='config_updated',
                metadata={
                    'config_key': config.key,
                    'old_value': old_value,
                    'new_value': new_value,
                    'category': config.category
                }
            )
            
            messages.success(request, f'Configuration "{config.key}" updated successfully.')
        else:
            messages.error(request, f'Error updating configuration: {form.errors}')
        
        return redirect('admin_tools:system_config')


class BulkConfigurationUpdateView(AdminRequiredMixin, View):
    """Update multiple configurations at once"""
    
    def post(self, request):
        form = BulkConfigurationForm(request.POST)
        
        if form.is_valid():
            category = form.cleaned_data['category']
            configs = SystemConfiguration.objects.filter(category=category)
            
            updated_count = 0
            for config in configs:
                field_name = f'config_{config.id}'
                if field_name in request.POST:
                    old_value = config.value
                    new_value = request.POST[field_name]
                    
                    if old_value != new_value:
                        config.value = new_value
                        config.save()
                        
                        # Clear cache
                        cache_key = f'system_config_{config.key}'
                        cache.delete(cache_key)
                        
                        # Log individual change
                        AdminAuditService.log_action(
                            admin_user=request.user,
                            action_type='config_updated',
                            metadata={
                                'config_key': config.key,
                                'old_value': old_value,
                                'new_value': new_value,
                                'category': config.category
                            }
                        )
                        
                        updated_count += 1
            
            messages.success(request, f'{updated_count} configurations updated successfully.')
        else:
            messages.error(request, f'Error updating configurations: {form.errors}')
        
        return redirect('admin_tools:system_config')


# ===== SYSTEM HEALTH VIEWS =====

class SystemHealthView(AdminRequiredMixin, TemplateView):
    """View system health status"""
    
    template_name = 'admin_tools/health/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get latest health check
        try:
            latest_check = SystemHealthCheck.objects.latest('created_at')
            context['latest_check'] = latest_check
        except SystemHealthCheck.DoesNotExist:
            context['latest_check'] = None
        
        # Get health check history
        health_checks = SystemHealthCheck.objects.all().order_by('-created_at')[:20]
        context['health_history'] = health_checks
        
        # Calculate statistics
        total_checks = SystemHealthCheck.objects.count()
        failed_checks = SystemHealthCheck.objects.filter(status='critical').count()
        
        if total_checks > 0:
            context['success_rate'] = ((total_checks - failed_checks) / total_checks) * 100
        else:
            context['success_rate'] = 100
        
        # Get current system status
        context['current_status'] = SystemHealthService.check_system_health()
        
        return context


class SystemHealthCheckView(AdminRequiredMixin, View):
    """Run a system health check"""
    
    def post(self, request):
        try:
            health_check = SystemHealthService.perform_health_check()
            
            # Log the health check
            AdminAuditService.log_action(
                admin_user=request.user,
                action_type='health_check_run',
                metadata={
                    'status': health_check.status,
                    'response_time': health_check.response_time,
                    'issues_count': len(health_check.issues)
                }
            )
            
            messages.success(request, 'System health check completed successfully.')
        except Exception as e:
            messages.error(request, f'Error running health check: {str(e)}')
        
        return redirect('admin_tools:system_health')


class SystemHealthDetailView(AdminRequiredMixin, DetailView):
    """View detailed health check results"""
    
    model = SystemHealthCheck
    template_name = 'admin_tools/health/detail.html'
    context_object_name = 'health_check'


# ===== NOTIFICATION PREFERENCES VIEWS =====

class NotificationPreferencesView(AdminRequiredMixin, View):
    """Manage admin notification preferences"""
    
    def get(self, request):
        try:
            preferences = AdminNotificationPreference.objects.get(user=request.user)
            form = AdminNotificationPreferenceForm(instance=preferences)
        except AdminNotificationPreference.DoesNotExist:
            form = AdminNotificationPreferenceForm()
        
        return render(request, 'admin_tools/notifications/preferences.html', {
            'form': form
        })
    
    def post(self, request):
        try:
            preferences = AdminNotificationPreference.objects.get(user=request.user)
            form = AdminNotificationPreferenceForm(request.POST, instance=preferences)
        except AdminNotificationPreference.DoesNotExist:
            form = AdminNotificationPreferenceForm(request.POST)
        
        if form.is_valid():
            preferences = form.save(commit=False)
            preferences.user = request.user
            preferences.save()
            
            messages.success(request, 'Notification preferences updated successfully.')
        else:
            messages.error(request, 'Error updating preferences.')
        
        return redirect('admin_tools:notification_preferences')


# ===== AJAX VIEWS =====

class TaskCalendarView(AdminRequiredMixin, View):
    """Get tasks for calendar view"""
    
    def get(self, request):
        start = request.GET.get('start')
        end = request.GET.get('end')
        
        tasks = AdminTask.objects.filter(
            due_date__range=[start, end]
        ).select_related('assigned_to')
        
        events = []
        for task in tasks:
            # Determine color based on priority
            color_map = {
                'high': '#dc3545',    # Red
                'medium': '#ffc107',   # Yellow
                'low': '#28a745'       # Green
            }
            
            events.append({
                'id': task.id,
                'title': task.title,
                'start': task.due_date.isoformat(),
                'url': reverse_lazy('admin_tools:task_detail', kwargs={'pk': task.id}),
                'color': color_map.get(task.priority, '#007bff'),
                'extendedProps': {
                    'priority': task.priority,
                    'status': task.status,
                    'assigned_to': task.assigned_to.username if task.assigned_to else 'Unassigned'
                }
            })
        
        return JsonResponse(events, safe=False)


class DashboardStatisticsView(AdminRequiredMixin, View):
    """Get dashboard statistics for AJAX updates"""
    
    def get(self, request):
        today = timezone.now().date()
        week_ago = today - timezone.timedelta(days=7)
        
        statistics = {
            'total_users': User.objects.filter(is_active=True).count(),
            'total_writers': WriterProfile.objects.filter(is_approved=True).count(),
            'total_orders': Order.objects.count(),
            'active_orders': Order.objects.filter(
                status__in=['assigned', 'in_progress']
            ).count(),
            'pending_writer_reviews': WriterProfile.objects.filter(
                verification_status='under_admin_review'
            ).count(),
            'my_pending_tasks': AdminTask.objects.filter(
                assigned_to=request.user,
                status__in=['pending', 'in_progress']
            ).count(),
            'overdue_tasks': AdminTask.objects.filter(
                due_date__lt=timezone.now(),
                status__in=['pending', 'in_progress']
            ).count(),
            'recent_orders': Order.objects.filter(
                created_at__date=today
            ).count(),
            'weekly_orders': Order.objects.filter(
                created_at__gte=week_ago
            ).count(),
            'weekly_revenue': Payment.objects.filter(
                status='completed',
                created_at__gte=week_ago
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
        }
        
        return JsonResponse(statistics)


class AdminQuickActionView(AdminRequiredMixin, View):
    """Handle quick actions from admin dashboard"""
    
    def post(self, request):
        action = request.POST.get('action')
        
        if action == 'create_task':
            # Quick task creation
            title = request.POST.get('title')
            description = request.POST.get('description')
            
            if title:
                task = AdminTask.objects.create(
                    title=title,
                    description=description or '',
                    created_by=request.user,
                    assigned_to=request.user,
                    priority='medium',
                    due_date=timezone.now() + timezone.timedelta(days=3)
                )
                
                AdminAuditService.log_action(
                    admin_user=request.user,
                    action_type='task_created',
                    metadata={
                        'task_id': task.id,
                        'title': task.title,
                        'quick_action': True
                    }
                )
                
                messages.success(request, 'Quick task created successfully.')
                return JsonResponse({'success': True, 'task_id': task.id})
        
        elif action == 'run_health_check':
            # Quick health check
            try:
                health_check = SystemHealthService.perform_health_check()
                return JsonResponse({
                    'success': True,
                    'status': health_check.status,
                    'issues_count': len(health_check.issues)
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
        
        return JsonResponse({'success': False, 'error': 'Invalid action'})


# ===== ADD THESE VIEWS TO YOUR EXISTING views.py =====

# Task assignment view (if not already in your views)
class TaskAssignView(AdminRequiredMixin, View):
    """Assign a task to a user"""
    
    def get(self, request, pk):
        task = get_object_or_404(AdminTask, pk=pk)
        form = TaskAssignmentForm(instance=task)
        return render(request, 'admin_tools/tasks/assign.html', {
            'task': task,
            'form': form
        })
    
    def post(self, request, pk):
        task = get_object_or_404(AdminTask, pk=pk)
        form = TaskAssignmentForm(request.POST, instance=task)
        
        if form.is_valid():
            old_assignee = task.assigned_to
            task = form.save()
            
            AdminAuditService.log_action(
                admin_user=request.user,
                action_type='task_assigned',
                target_user=old_assignee,
                metadata={
                    'task_id': task.id,
                    'old_assignee_id': old_assignee.id if old_assignee else None,
                    'new_assignee_id': task.assigned_to.id if task.assigned_to else None
                }
            )
            
            messages.success(request, f'Task "{task.title}" assigned successfully.')
            return redirect('admin_tools:task_detail', pk=task.pk)
        
        return render(request, 'admin_tools/tasks/assign.html', {
            'task': task,
            'form': form
        })


class TaskCompleteView(AdminRequiredMixin, View):
    """Complete a task with results"""
    
    def get(self, request, pk):
        task = get_object_or_404(AdminTask, pk=pk)
        form = TaskCompletionForm()
        return render(request, 'admin_tools/tasks/complete.html', {
            'task': task,
            'form': form
        })
    
    def post(self, request, pk):
        task = get_object_or_404(AdminTask, pk=pk)
        form = TaskCompletionForm(request.POST, request.FILES)
        
        if form.is_valid():
            task.status = 'completed'
            task.completed_at = timezone.now()
            task.completion_notes = form.cleaned_data['result']
            task.actual_hours = form.cleaned_data['actual_hours'] or task.estimated_hours
            task.save()
            
            AdminAuditService.log_action(
                admin_user=request.user,
                action_type='task_completed',
                target_user=task.assigned_to,
                metadata={
                    'task_id': task.id,
                    'actual_hours': task.actual_hours,
                    'completion_notes': task.completion_notes[:100]  # First 100 chars
                }
            )
            
            messages.success(request, f'Task "{task.title}" completed successfully.')
            return redirect('admin_tools:task_detail', pk=task.pk)
        
        return render(request, 'admin_tools/tasks/complete.html', {
            'task': task,
            'form': form
        })


class TaskCancelView(AdminRequiredMixin, View):
    """Cancel a task"""
    
    def post(self, request, pk):
        task = get_object_or_404(AdminTask, pk=pk)
        
        if task.status not in ['pending', 'in_progress']:
            messages.error(request, f'Task cannot be cancelled from status: {task.status}')
            return redirect('admin_tools:task_detail', pk=task.pk)
        
        old_status = task.status
        task.status = 'cancelled'
        task.cancelled_at = timezone.now()
        task.cancelled_by = request.user
        task.save()
        
        AdminAuditService.log_action(
            admin_user=request.user,
            action_type='task_cancelled',
            target_user=task.assigned_to,
            metadata={
                'task_id': task.id,
                'old_status': old_status
            }
        )
        
        messages.success(request, f'Task "{task.title}" cancelled successfully.')
        return redirect('admin_tools:task_detail', pk=task.pk)


class MyTasksView(AdminRequiredMixin, ListView):
    """View tasks assigned to current user"""
    
    model = AdminTask
    template_name = 'admin_tools/tasks/my_tasks.html'
    context_object_name = 'tasks'
    paginate_by = 25
    
    def get_queryset(self):
        return AdminTask.objects.filter(
            assigned_to=self.request.user,
            status__in=['pending', 'in_progress']
        ).select_related('created_by', 'related_order').order_by('due_date', '-priority')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_my_tasks'] = self.get_queryset().count()
        context['overdue_my_tasks'] = AdminTask.objects.filter(
            assigned_to=self.request.user,
            status__in=['pending', 'in_progress'],
            due_date__lt=timezone.now()
        ).count()
        return context


class TaskStatisticsView(AdminRequiredMixin, TemplateView):
    """View task statistics"""
    
    template_name = 'admin_tools/tasks/statistics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate statistics for different time periods
        today = timezone.now().date()
        week_ago = today - timezone.timedelta(days=7)
        month_ago = today - timezone.timedelta(days=30)
        
        # Overall statistics
        context['total_tasks'] = AdminTask.objects.count()
        context['completed_tasks'] = AdminTask.objects.filter(status='completed').count()
        context['pending_tasks'] = AdminTask.objects.filter(status__in=['pending', 'in_progress']).count()
        context['overdue_tasks'] = AdminTask.objects.filter(
            status__in=['pending', 'in_progress'],
            due_date__lt=timezone.now()
        ).count()
        
        # Recent statistics
        context['tasks_today'] = AdminTask.objects.filter(created_at__date=today).count()
        context['tasks_this_week'] = AdminTask.objects.filter(created_at__gte=week_ago).count()
        context['tasks_this_month'] = AdminTask.objects.filter(created_at__gte=month_ago).count()
        
        # Completion rate
        if context['total_tasks'] > 0:
            context['completion_rate'] = (context['completed_tasks'] / context['total_tasks']) * 100
        else:
            context['completion_rate'] = 0
        
        # Tasks by priority
        context['high_priority'] = AdminTask.objects.filter(priority='high').count()
        context['medium_priority'] = AdminTask.objects.filter(priority='medium').count()
        context['low_priority'] = AdminTask.objects.filter(priority='low').count()
        
        # Average completion time
        completed_tasks = AdminTask.objects.filter(
            status='completed',
            started_at__isnull=False,
            completed_at__isnull=False
        )
        
        if completed_tasks.exists():
            total_duration = sum(
                (task.completed_at - task.started_at).total_seconds()
                for task in completed_tasks
            )
            context['avg_completion_hours'] = total_duration / completed_tasks.count() / 3600
        else:
            context['avg_completion_hours'] = 0
        
        return context


# ===== WRITER MANAGEMENT VIEWS =====

class WriterReviewListView(AdminRequiredMixin, ListView):
    """List writers pending review"""
    
    template_name = 'admin_tools/writer_review/list.html'
    context_object_name = 'writers'
    paginate_by = 20
    
    def get_queryset(self):
        from apps.accounts.models import WriterProfile
        return WriterProfile.objects.filter(
            verification_status='under_admin_review'
        ).select_related('user').order_by('created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_pending'] = self.get_queryset().count()
        return context


class WriterReviewDetailView(AdminRequiredMixin, DetailView):
    """View writer details for review"""
    
    template_name = 'admin_tools/writer_review/detail.html'
    context_object_name = 'writer_profile'
    
    def get_object(self):
        from apps.accounts.models import WriterProfile
        writer_id = self.kwargs.get('writer_id')
        return get_object_or_404(WriterProfile, id=writer_id)


# ===== ORDER ASSIGNMENT VIEWS =====

class OrderAssignmentListView(AdminRequiredMixin, ListView):
    """List orders pending assignment"""
    
    template_name = 'admin_tools/order_assignment/list.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        return Order.objects.filter(
            status='paid',
            assigned_writer__isnull=True
        ).select_related('client').order_by('created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_pending'] = self.get_queryset().count()
        return context