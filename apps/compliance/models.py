import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings


class ConsentLog(models.Model):
    """Log user consent for GDPR compliance."""
    
    class ConsentType(models.TextChoices):
        REGISTRATION = 'registration', _('Registration')
        TERMS = 'terms', _('Terms of Service')
        PRIVACY = 'privacy', _('Privacy Policy')
        MARKETING = 'marketing', _('Marketing Emails')
        COOKIES = 'cookies', _('Cookies')
        DATA_PROCESSING = 'data_processing', _('Data Processing')
    
    log_id = models.UUIDField(
        _('log ID'),
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consent_logs',
        verbose_name=_('user')
    )
    
    consent_type = models.CharField(
        _('consent type'),
        max_length=50,
        choices=ConsentType.choices,
    )
    
    consent_given = models.BooleanField(
        _('consent given'),
        default=True,
        help_text=_('Whether consent was given (True) or withdrawn (False)')
    )
    
    ip_address = models.GenericIPAddressField(
        _('IP address'),
        null=True,
        blank=True,
    )
    
    user_agent = models.TextField(
        _('user agent'),
        blank=True,
    )
    
    consent_text = models.TextField(
        _('consent text'),
        blank=True,
        help_text=_('Exact text of what was consented to')
    )
    
    version = models.CharField(
        _('version'),
        max_length=20,
        blank=True,
        help_text=_('Version of terms/privacy policy at time of consent')
    )
    
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
    )
    
    class Meta:
        verbose_name = _('consent log')
        verbose_name_plural = _('consent logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'consent_type']),
            models.Index(fields=['consent_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        action = "Consented to" if self.consent_given else "Withdrew consent for"
        return f'{self.user.email} - {action} {self.get_consent_type_display()}'


class DataRequest(models.Model):
    """Track GDPR data subject access requests."""
    
    class RequestType(models.TextChoices):
        ACCESS = 'access', _('Data Access Request')
        RECTIFICATION = 'rectification', _('Data Rectification')
        ERASURE = 'erasure', _('Right to be Forgotten')
        RESTRICTION = 'restriction', _('Processing Restriction')
        PORTABILITY = 'portability', _('Data Portability')
        OBJECTION = 'objection', _('Objection to Processing')
    
    class RequestStatus(models.TextChoices):
        RECEIVED = 'received', _('Received')
        VERIFYING = 'verifying', _('Verifying Identity')
        PROCESSING = 'processing', _('Processing')
        COMPLETED = 'completed', _('Completed')
        REJECTED = 'rejected', _('Rejected')
        APPEALED = 'appealed', _('Appealed')
    
    request_id = models.UUIDField(
        _('request ID'),
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='data_requests',
        verbose_name=_('user')
    )
    
    request_type = models.CharField(
        _('request type'),
        max_length=50,
        choices=RequestType.choices,
    )
    
    status = models.CharField(
        _('status'),
        max_length=50,
        choices=RequestStatus.choices,
        default=RequestStatus.RECEIVED,
    )
    
    description = models.TextField(
        _('description'),
        help_text=_('Detailed description of the request')
    )
    
    # Verification details
    verification_method = models.CharField(
        _('verification method'),
        max_length=100,
        blank=True,
        help_text=_('Method used to verify user identity')
    )
    
    verification_date = models.DateTimeField(
        _('verification date'),
        null=True,
        blank=True,
    )
    
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_requests',
        verbose_name=_('verified by')
    )
    
    # Processing details
    processing_notes = models.TextField(
        _('processing notes'),
        blank=True,
        help_text=_('Internal notes about request processing')
    )
    
    data_provided = models.TextField(
        _('data provided'),
        blank=True,
        help_text=_('Summary of data provided to user')
    )
    
    file_path = models.CharField(
        _('file path'),
        max_length=500,
        blank=True,
        help_text=_('Path to exported data file')
    )
    
    # Rejection details
    rejection_reason = models.TextField(
        _('rejection reason'),
        blank=True,
        help_text=_('Reason for request rejection if applicable')
    )
    
    appeal_notes = models.TextField(
        _('appeal notes'),
        blank=True,
    )
    
    # Legal timeframe tracking
    received_at = models.DateTimeField(
        _('received at'),
        auto_now_add=True,
    )
    
    due_date = models.DateTimeField(
        _('due date'),
        help_text=_('Legal deadline for request completion (30 days from receipt)')
    )
    
    completed_at = models.DateTimeField(
        _('completed at'),
        null=True,
        blank=True,
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
    )
    
    class Meta:
        verbose_name = _('data request')
        verbose_name_plural = _('data requests')
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['request_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['request_type']),
        ]
    
    def __str__(self):
        return f'Data Request {self.request_id} - {self.get_request_type_display()}'
    
    def save(self, *args, **kwargs):
        """Set due date on creation."""
        if not self.due_date:
            self.due_date = timezone.now() + timezone.timedelta(days=30)
        super().save(*args, **kwargs)
    
    @property
    def is_overdue(self):
        """Check if request is overdue."""
        return timezone.now() > self.due_date and self.status != self.RequestStatus.COMPLETED
    
    @property
    def days_remaining(self):
        """Calculate days remaining until deadline."""
        remaining = self.due_date - timezone.now()
        return max(remaining.days, 0)
    
    @property
    def requires_urgent_action(self):
        """Check if request requires urgent action."""
        return self.days_remaining <= 7 and self.status not in [
            self.RequestStatus.COMPLETED, self.RequestStatus.REJECTED
        ]


class DataRetentionRule(models.Model):
    """Rules for automatic data retention and deletion."""
    
    class DataType(models.TextChoices):
        USER_ACCOUNT = 'user_account', _('User Account')
        ORDER_DATA = 'order_data', _('Order Data')
        PAYMENT_DATA = 'payment_data', _('Payment Data')
        COMMUNICATION = 'communication', _('Communication')
        LOGS = 'logs', _('System Logs')
        BACKUPS = 'backups', _('Backup Data')
    
    class ActionType(models.TextChoices):
        ANONYMIZE = 'anonymize', _('Anonymize')
        DELETE = 'delete', _('Delete')
        ARCHIVE = 'archive', _('Archive')
    
    rule_name = models.CharField(
        _('rule name'),
        max_length=200,
        unique=True,
    )
    
    data_type = models.CharField(
        _('data type'),
        max_length=50,
        choices=DataType.choices,
    )
    
    retention_period_days = models.PositiveIntegerField(
        _('retention period (days)'),
        help_text=_('Number of days to retain data before taking action')
    )
    
    action_type = models.CharField(
        _('action type'),
        max_length=50,
        choices=ActionType.choices,
    )
    
    is_active = models.BooleanField(
        _('is active'),
        default=True,
    )
    
    description = models.TextField(
        _('description'),
        blank=True,
        help_text=_('Detailed description of the rule')
    )
    
    # Legal basis
    legal_basis = models.TextField(
        _('legal basis'),
        blank=True,
        help_text=_('Legal basis for retention period (GDPR Article)')
    )
    
    # Execution tracking
    last_executed = models.DateTimeField(
        _('last executed'),
        null=True,
        blank=True,
    )
    
    items_processed = models.PositiveIntegerField(
        _('items processed'),
        default=0,
    )
    
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True,
    )
    
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True,
    )
    
    class Meta:
        verbose_name = _('data retention rule')
        verbose_name_plural = _('data retention rules')
        ordering = ['data_type', 'retention_period_days']
    
    def __str__(self):
        return f'{self.rule_name} - {self.retention_period_days} days'
    
    def execute(self, dry_run=False):
        """
        Execute the retention rule.
        
        Args:
            dry_run: If True, only simulate execution
            
        Returns:
            Dictionary with execution results
        """
        from .services import DataRetentionService
        
        service = DataRetentionService()
        results = service.execute_rule(self, dry_run)
        
        if not dry_run:
            self.last_executed = timezone.now()
            self.items_processed = results.get('processed_count', 0)
            self.save()
        
        return results


class AuditLog(models.Model):
    """Comprehensive audit logging for compliance."""
    
    class ActionType(models.TextChoices):
        CREATE = 'create', _('Create')
        UPDATE = 'update', _('Update')
        DELETE = 'delete', _('Delete')
        VIEW = 'view', _('View')
        LOGIN = 'login', _('Login')
        LOGOUT = 'logout', _('Logout')
        EXPORT = 'export', _('Export')
        IMPORT = 'import', _('Import')
    
    log_id = models.UUIDField(
        _('log ID'),
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_('user')
    )
    
    action_type = models.CharField(
        _('action type'),
        max_length=50,
        choices=ActionType.choices,
    )
    
    model_name = models.CharField(
        _('model name'),
        max_length=100,
        help_text=_('Name of the Django model')
    )
    
    object_id = models.CharField(
        _('object ID'),
        max_length=100,
        blank=True,
        help_text=_('ID of the affected object')
    )
    
    # Detailed information
    changes = models.JSONField(
        _('changes'),
        null=True,
        blank=True,
        help_text=_('Detailed changes made (JSON format)')
    )
    
    before_state = models.JSONField(
        _('before state'),
        null=True,
        blank=True,
        help_text=_('Object state before action')
    )
    
    after_state = models.JSONField(
        _('after state'),
        null=True,
        blank=True,
        help_text=_('Object state after action')
    )
    
    # Context information
    ip_address = models.GenericIPAddressField(
        _('IP address'),
        null=True,
        blank=True,
    )
    
    user_agent = models.TextField(
        _('user agent'),
        blank=True,
    )
    
    request_path = models.CharField(
        _('request path'),
        max_length=500,
        blank=True,
    )
    
    session_key = models.CharField(
        _('session key'),
        max_length=100,
        blank=True,
    )
    
    # Timestamps
    timestamp = models.DateTimeField(
        _('timestamp'),
        auto_now_add=True,
        db_index=True,
    )
    
    class Meta:
        verbose_name = _('audit log')
        verbose_name_plural = _('audit logs')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['log_id']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action_type', 'timestamp']),
        ]
    
    def __str__(self):
        return f'{self.action_type} on {self.model_name} by {self.user or "System"}'