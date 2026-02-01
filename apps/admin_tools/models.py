import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator


class AdminAuditLog(models.Model):
    """Audit log for admin actions"""
    
    class ActionType(models.TextChoices):
        WRITER_APPROVAL = 'writer_approval', 'Writer Approval'
        WRITER_REJECTION = 'writer_rejection', 'Writer Rejection'
        ORDER_ASSIGNMENT = 'order_assignment', 'Order Assignment'
        DISPUTE_RESOLUTION = 'dispute_resolution', 'Dispute Resolution'
        REFUND_PROCESSING = 'refund_processing', 'Refund Processing'
        CONTENT_MODERATION = 'content_moderation', 'Content Moderation'
        SYSTEM_CONFIG_CHANGE = 'system_config_change', 'System Config Change'
        USER_MANAGEMENT = 'user_management', 'User Management'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_actions'
    )
    
    action_type = models.CharField(max_length=50, choices=ActionType.choices)
    action_description = models.TextField()
    
    # Target object references
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_actions_against'
    )
    target_order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    target_payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Changes made
    previous_state = models.JSONField(default=dict, blank=True)
    new_state = models.JSONField(default=dict, blank=True)
    changes_summary = models.TextField(blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Admin Audit Log"
        verbose_name_plural = "Admin Audit Logs"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action_type', 'created_at']),
            models.Index(fields=['admin_user', 'created_at']),
            models.Index(fields=['target_user', 'created_at']),
        ]
        permissions = [
            ('can_view_audit_logs', 'Can view admin audit logs'),
            ('can_export_audit_logs', 'Can export admin audit logs'),
        ]

    def __str__(self):
        return f"{self.get_action_type_display()} by {self.admin_user} at {self.created_at}"


class AdminTask(models.Model):
    """Admin tasks and assignments"""
    
    class TaskType(models.TextChoices):
        WRITER_REVIEW = 'writer_review', 'Writer Review'
        ORDER_ASSIGNMENT = 'order_assignment', 'Order Assignment'
        DISPUTE_RESOLUTION = 'dispute_resolution', 'Dispute Resolution'
        REFUND_REVIEW = 'refund_review', 'Refund Review'
        CONTENT_MODERATION = 'content_moderation', 'Content Moderation'
        SYSTEM_MAINTENANCE = 'system_maintenance', 'System Maintenance'
        DATA_CLEANUP = 'data_cleanup', 'Data Cleanup'
    
    class TaskPriority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'
    
    class TaskStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        ON_HOLD = 'on_hold', 'On Hold'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    task_type = models.CharField(max_length=50, choices=TaskType.choices)
    priority = models.CharField(max_length=20, choices=TaskPriority.choices, default=TaskPriority.MEDIUM)
    status = models.CharField(max_length=20, choices=TaskStatus.choices, default=TaskStatus.PENDING)
    
    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_tasks',
        limit_choices_to={'is_staff': True}
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_admin_tasks'
    )
    
    # Target references
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_tasks_against'
    )
    target_order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Due dates
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Notes and results
    notes = models.TextField(blank=True)
    result = models.TextField(blank=True)
    attachments = ArrayField(
        models.URLField(),
        blank=True,
        default=list
    )
    
    # Metadata
    estimated_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    actual_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Admin Task"
        verbose_name_plural = "Admin Tasks"
        ordering = ['-priority', 'due_date', '-created_at']
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['task_type', 'status']),
        ]
        permissions = [
            ('can_assign_tasks', 'Can assign admin tasks'),
            ('can_view_all_tasks', 'Can view all admin tasks'),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    def is_overdue(self):
        if self.due_date and self.status not in [self.TaskStatus.COMPLETED, self.TaskStatus.CANCELLED]:
            return self.due_date < timezone.now()
        return False
    
    def mark_completed(self, result_text=""):
        self.status = self.TaskStatus.COMPLETED
        self.completed_at = timezone.now()
        if result_text:
            self.result = result_text
        self.save()


class SystemConfiguration(models.Model):
    """System-wide configuration settings"""
    
    class ConfigCategory(models.TextChoices):
        PLATFORM = 'platform', 'Platform Settings'
        PAYMENT = 'payment', 'Payment Settings'
        WRITER = 'writer', 'Writer Settings'
        ORDER = 'order', 'Order Settings'
        NOTIFICATION = 'notification', 'Notification Settings'
        SECURITY = 'security', 'Security Settings'
        COMPLIANCE = 'compliance', 'Compliance Settings'
    
    key = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50, choices=ConfigCategory.choices)
    
    # Value storage
    value_string = models.CharField(max_length=500, blank=True)
    value_number = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)
    value_json = models.JSONField(null=True, blank=True)
    
    # Metadata
    display_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    help_text = models.TextField(blank=True)
    
    # Validation
    validation_regex = models.CharField(max_length=200, blank=True)
    min_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    max_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    allowed_values = ArrayField(
        models.CharField(max_length=100),
        blank=True,
        default=list
    )
    
    # Access control
    is_editable = models.BooleanField(default=True)
    requires_restart = models.BooleanField(default=False)
    
    # Audit
    last_modified = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "System Configuration"
        verbose_name_plural = "System Configurations"
        ordering = ['category', 'key']
        indexes = [
            models.Index(fields=['category', 'key']),
        ]
        permissions = [
            ('can_manage_configuration', 'Can manage system configuration'),
        ]

    def __str__(self):
        return f"{self.display_name} ({self.key})"
    
    @property
    def value(self):
        """Get the appropriate value based on type"""
        if self.value_string is not None and self.value_string != '':
            return self.value_string
        elif self.value_number is not None:
            return float(self.value_number)
        elif self.value_boolean is not None:
            return self.value_boolean
        elif self.value_json is not None:
            return self.value_json
        return None
    
    @value.setter
    def value(self, val):
        """Set the appropriate value based on type"""
        if isinstance(val, str):
            self.value_string = val
            self.value_number = None
            self.value_boolean = None
            self.value_json = None
        elif isinstance(val, (int, float)):
            self.value_number = val
            self.value_string = ''
            self.value_boolean = None
            self.value_json = None
        elif isinstance(val, bool):
            self.value_boolean = val
            self.value_string = ''
            self.value_number = None
            self.value_json = None
        elif isinstance(val, (dict, list)):
            self.value_json = val
            self.value_string = ''
            self.value_number = None
            self.value_boolean = None
        else:
            self.value_string = str(val)
            self.value_number = None
            self.value_boolean = None
            self.value_json = None


class AdminDashboardWidget(models.Model):
    """Customizable admin dashboard widgets"""
    
    class WidgetType(models.TextChoices):
        STATS_CARD = 'stats_card', 'Stats Card'
        LINE_CHART = 'line_chart', 'Line Chart'
        BAR_CHART = 'bar_chart', 'Bar Chart'
        PIE_CHART = 'pie_chart', 'Pie Chart'
        DATA_TABLE = 'data_table', 'Data Table'
        RECENT_ACTIVITY = 'recent_activity', 'Recent Activity'
        TASK_LIST = 'task_list', 'Task List'
    
    class WidgetSize(models.TextChoices):
        SMALL = 'small', 'Small (1x1)'
        MEDIUM = 'medium', 'Medium (2x1)'
        LARGE = 'large', 'Large (2x2)'
        XLARGE = 'xlarge', 'Extra Large (3x2)'
    
    name = models.CharField(max_length=100)
    widget_type = models.CharField(max_length=50, choices=WidgetType.choices)
    size = models.CharField(max_length=20, choices=WidgetSize.choices, default=WidgetSize.MEDIUM)
    
    # Configuration
    config = models.JSONField(default=dict)
    
    # Display
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=200, blank=True)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, default='primary')
    
    # Data source
    data_source = models.CharField(max_length=200, blank=True)
    refresh_interval = models.PositiveIntegerField(default=300)  # seconds
    
    # Position
    column = models.PositiveIntegerField(default=0)
    row = models.PositiveIntegerField(default=0)
    
    # Visibility
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    allowed_roles = ArrayField(
        models.CharField(max_length=50),
        blank=True,
        default=list
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dashboard Widget"
        verbose_name_plural = "Dashboard Widgets"
        ordering = ['column', 'row']
        unique_together = ['column', 'row']
    
    def __str__(self):
        return f"{self.name} ({self.get_widget_type_display()})"


class AdminNotificationPreference(models.Model):
    """Admin notification preferences"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_notification_preferences',
        limit_choices_to={'is_staff': True}
    )
    
    # Email notifications
    email_writer_approvals = models.BooleanField(default=True)
    email_order_assignments = models.BooleanField(default=True)
    email_dispute_alerts = models.BooleanField(default=True)
    email_refund_requests = models.BooleanField(default=True)
    email_system_alerts = models.BooleanField(default=True)
    email_compliance_issues = models.BooleanField(default=True)
    
    # In-app notifications
    inapp_writer_approvals = models.BooleanField(default=True)
    inapp_order_assignments = models.BooleanField(default=True)
    inapp_dispute_alerts = models.BooleanField(default=True)
    inapp_refund_requests = models.BooleanField(default=True)
    inapp_system_alerts = models.BooleanField(default=True)
    inapp_compliance_issues = models.BooleanField(default=True)
    
    # Frequency
    digest_frequency = models.CharField(
        max_length=20,
        choices=[
            ('never', 'Never'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
        ],
        default='daily'
    )
    
    # Quiet hours
    quiet_hours_start = models.TimeField(default='22:00')
    quiet_hours_end = models.TimeField(default='08:00')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Admin Notification Preference"
        verbose_name_plural = "Admin Notification Preferences"
    
    def __str__(self):
        return f"Notification Preferences - {self.user.get_full_name()}"


class SystemHealthCheck(models.Model):
    """System health check records"""
    
    class HealthStatus(models.TextChoices):
        HEALTHY = 'healthy', 'Healthy'
        WARNING = 'warning', 'Warning'
        CRITICAL = 'critical', 'Critical'
        OFFLINE = 'offline', 'Offline'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Service checks
    database_status = models.CharField(max_length=20, choices=HealthStatus.choices)
    cache_status = models.CharField(max_length=20, choices=HealthStatus.choices)
    celery_status = models.CharField(max_length=20, choices=HealthStatus.choices)
    email_status = models.CharField(max_length=20, choices=HealthStatus.choices)
    storage_status = models.CharField(max_length=20, choices=HealthStatus.choices)
    api_status = models.CharField(max_length=20, choices=HealthStatus.choices)
    
    # Metrics
    database_response_time = models.FloatField(help_text="Response time in milliseconds")
    cache_response_time = models.FloatField(help_text="Response time in milliseconds")
    server_load = models.FloatField(help_text="CPU load average")
    memory_usage = models.FloatField(help_text="Memory usage percentage")
    disk_usage = models.FloatField(help_text="Disk usage percentage")
    
    # Active counts
    active_users = models.PositiveIntegerField(default=0)
    active_orders = models.PositiveIntegerField(default=0)
    pending_tasks = models.PositiveIntegerField(default=0)
    queue_size = models.PositiveIntegerField(default=0)
    
    # Issues
    issues_found = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    
    # Overall status
    overall_status = models.CharField(max_length=20, choices=HealthStatus.choices)
    score = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "System Health Check"
        verbose_name_plural = "System Health Checks"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['overall_status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Health Check - {self.created_at.strftime('%Y-%m-%d %H:%M')} ({self.get_overall_status_display()})"