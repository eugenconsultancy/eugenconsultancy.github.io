from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid


class KPI(models.Model):
    """Key Performance Indicators"""
    KPI_TYPES = [
        ('financial', 'Financial'),
        ('operational', 'Operational'),
        ('quality', 'Quality'),
        ('customer', 'Customer'),
        ('writer', 'Writer'),
    ]
    
    PERIODS = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    kpi_type = models.CharField(max_length=20, choices=KPI_TYPES)
    description = models.TextField(blank=True)
    
    # Target settings
    target_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    min_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    max_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Calculation settings
    calculation_period = models.CharField(
        max_length=20,
        choices=PERIODS,
        default='daily'
    )
    calculation_query = models.TextField(blank=True)  # Optional raw SQL
    is_auto_calculated = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['kpi_type', 'name']
        verbose_name = 'KPI'
        verbose_name_plural = 'KPIs'
        indexes = [
            models.Index(fields=['slug', 'is_active']),
            models.Index(fields=['kpi_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_kpi_type_display()})"
    
    @property
    def current_value(self):
        """Get most recent value"""
        latest = self.values.order_by('-period_end').first()
        return latest.value if latest else None
    
    @property
    def trend(self):
        """Get trend (improving/declining)"""
        values = self.values.order_by('-period_end')[:2]
        if len(values) >= 2:
            return 'improving' if values[0].value > values[1].value else 'declining'
        return 'stable'
    
    @property
    def status(self):
        """Get KPI status based on thresholds"""
        current = self.current_value
        if current is None:
            return 'unknown'
        
        if self.min_threshold and current < self.min_threshold:
            return 'critical'
        elif self.max_threshold and current > self.max_threshold:
            return 'warning'
        elif self.target_value:
            if abs(current - self.target_value) / self.target_value <= 0.1:  # Within 10%
                return 'on_target'
        return 'acceptable'


class KPIValue(models.Model):
    """Historical KPI values"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kpi = models.ForeignKey(
        KPI,
        on_delete=models.CASCADE,
        related_name='values'
    )
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Additional metadata
    data_points = models.PositiveIntegerField(default=1)
    min_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    max_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    avg_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Context data
    context_data = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-period_end']
        verbose_name = 'KPI Value'
        verbose_name_plural = 'KPI Values'
        indexes = [
            models.Index(fields=['kpi', 'period_end']),
            models.Index(fields=['period_start', 'period_end']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['kpi', 'period_start', 'period_end'],
                name='unique_kpi_period'
            ),
        ]
    
    def __str__(self):
        return f"{self.kpi.name}: {self.value} ({self.period_end.date()})"


class Dashboard(models.Model):
    """Analytics dashboard configuration"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Layout configuration (stored as JSON)
    layout_config = models.JSONField(default=dict)
    
    # Access control
    is_public = models.BooleanField(default=False)
    accessible_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='accessible_dashboards'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_dashboards'
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Dashboard'
        verbose_name_plural = 'Dashboards'
    
    def __str__(self):
        return self.name
    
    @property
    def kpis(self):
        """Get KPIs for this dashboard"""
        return self.widgets.filter(kpi__isnull=False).select_related('kpi')


class DashboardWidget(models.Model):
    """Widget on a dashboard"""
    WIDGET_TYPES = [
        ('kpi', 'KPI Card'),
        ('chart', 'Chart'),
        ('table', 'Data Table'),
        ('metric', 'Single Metric'),
        ('gauge', 'Gauge'),
        ('trend', 'Trend Line'),
    ]
    
    CHART_TYPES = [
        ('line', 'Line Chart'),
        ('bar', 'Bar Chart'),
        ('pie', 'Pie Chart'),
        ('scatter', 'Scatter Plot'),
        ('area', 'Area Chart'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='widgets'
    )
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    title = models.CharField(max_length=100)
    
    # KPI reference (for KPI widgets)
    kpi = models.ForeignKey(
        KPI,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='widgets'
    )
    
    # Chart configuration
    chart_type = models.CharField(
        max_length=20,
        choices=CHART_TYPES,
        null=True,
        blank=True
    )
    data_query = models.TextField(blank=True)  # Custom query for chart/data
    
    # Display settings
    width = models.PositiveIntegerField(default=4)  # Grid columns (1-12)
    height = models.PositiveIntegerField(default=300)  # Pixels
    position_x = models.PositiveIntegerField(default=0)
    position_y = models.PositiveIntegerField(default=0)
    
    # Configuration
    config = models.JSONField(default=dict, blank=True)
    refresh_interval = models.PositiveIntegerField(default=300)  # Seconds
    
    sort_order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order', 'created_at']
        verbose_name = 'Dashboard Widget'
        verbose_name_plural = 'Dashboard Widgets'
    
    def __str__(self):
        return f"{self.title} ({self.get_widget_type_display()})"


class Report(models.Model):
    """Analytics report"""
    REPORT_TYPES = [
        ('financial', 'Financial Report'),
        ('performance', 'Performance Report'),
        ('quality', 'Quality Report'),
        ('operational', 'Operational Report'),
        ('custom', 'Custom Report'),
    ]
    
    FORMATS = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('html', 'HTML'),
    ]
    
    SCHEDULES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('manual', 'Manual Only'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    description = models.TextField(blank=True)
    
    # Configuration
    data_query = models.TextField(blank=True)  # SQL or query definition
    template_path = models.CharField(max_length=500, blank=True)
    default_format = models.CharField(max_length=10, choices=FORMATS, default='pdf')
    
    # Scheduling
    schedule = models.CharField(
        max_length=20,
        choices=SCHEDULES,
        default='manual'
    )
    schedule_day = models.PositiveIntegerField(null=True, blank=True)  # Day of month/week
    schedule_time = models.TimeField(null=True, blank=True)
    
    # Recipients
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='subscribed_reports'
    )
    email_subject = models.CharField(max_length=200, blank=True)
    email_template = models.TextField(blank=True)
    
    # Access control
    is_public = models.BooleanField(default=False)
    accessible_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='accessible_reports'
    )
    
    # Metadata
    last_generated_at = models.DateTimeField(null=True, blank=True)
    last_generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_reports'
    )
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_reports'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'
        indexes = [
            models.Index(fields=['slug', 'is_active']),
            models.Index(fields=['report_type', 'is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def next_schedule(self):
        """Calculate next scheduled run"""
        if self.schedule == 'manual':
            return None
        
        from datetime import datetime, timedelta
        now = timezone.now()
        
        if self.schedule == 'daily':
            next_time = datetime.combine(now.date(), self.schedule_time)
            if next_time <= now:
                next_time += timedelta(days=1)
            return next_time
        
        # Implement weekly/monthly scheduling logic
        return None


class ReportExecution(models.Model):
    """Report execution log"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Execution details
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    
    # Output
    output_format = models.CharField(max_length=10, choices=Report.FORMATS)
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    
    # Parameters
    parameters = models.JSONField(default=dict, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    
    # Context
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='triggered_reports'
    )
    triggered_from = models.CharField(max_length=50, blank=True)  # web, api, scheduled, etc.
    error_message = models.TextField(blank=True)
    logs = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Report Execution'
        verbose_name_plural = 'Report Executions'
        indexes = [
            models.Index(fields=['report', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.report.name} - {self.created_at}"
    
    @property
    def is_successful(self):
        return self.status == 'completed'
    
    def mark_running(self):
        self.status = 'running'
        self.started_at = timezone.now()
        self.save()
    
    def mark_completed(self, file_path=None, file_size=None):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        if file_path:
            self.file_path = file_path
        if file_size:
            self.file_size = file_size
        self.save()
    
    def mark_failed(self, error_message):
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        self.save()