from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.admin import SimpleListFilter
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import csv
from django.http import HttpResponse


from .models.kpi import KPI, KPIValue, Dashboard, DashboardWidget, Report, ReportExecution
from .services.report_generator import AnalyticsService


class KPIStatusFilter(SimpleListFilter):
    """Filter KPIs by status"""
    title = 'Status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return [
            ('on_target', 'On Target'),
            ('warning', 'Warning'),
            ('critical', 'Critical'),
            ('unknown', 'Unknown Status'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'on_target':
            return queryset.filter(
                Q(target_value__isnull=False) &
                Q(values__isnull=False)
            )
        # Note: Status calculation would be more complex in reality
        return queryset


@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'kpi_type_display', 'current_value_display',
        'target_value_display', 'status_display', 'calculation_period',
        'is_active', 'last_updated'
    ]
    list_filter = [
        'kpi_type', 'calculation_period', 'is_active', KPIStatusFilter
    ]
    search_fields = ['name', 'slug', 'description']
    readonly_fields = [
        'slug', 'created_at', 'updated_at', 'current_value',
        'trend', 'status'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'kpi_type', 'description')
        }),
        ('Target Settings', {
            'fields': ('target_value', 'min_threshold', 'max_threshold')
        }),
        ('Calculation Settings', {
            'fields': ('calculation_period', 'calculation_query', 'is_auto_calculated')
        }),
        ('Status Information', {
            'fields': ('current_value', 'trend', 'status'),
            'classes': ('collapse',)
        }),
        ('Administration', {
            'fields': ('is_active', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['calculate_selected_kpis', 'export_kpis_csv', 'activate_kpis', 'deactivate_kpis']
    
    def kpi_type_display(self, obj):
        color_map = {
            'financial': '#4CAF50',
            'operational': '#2196F3',
            'quality': '#FF9800',
            'customer': '#9C27B0',
            'writer': '#607D8B',
        }
        color = color_map.get(obj.kpi_type, '#666')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_kpi_type_display()
        )
    kpi_type_display.short_description = 'Type'
    
    def current_value_display(self, obj):
        current = obj.current_value
        if current is None:
            return format_html('<span style="color: #999;">No data</span>')
        
        # Format based on KPI type
        if obj.kpi_type == 'financial':
            return format_html('<strong>${:,.2f}</strong>', current)
        elif obj.kpi_type == 'quality':
            return format_html('<strong>{:.2f}</strong>', current)
        else:
            return format_html('<strong>{:,.0f}</strong>', current)
    current_value_display.short_description = 'Current Value'
    
    def target_value_display(self, obj):
        if obj.target_value:
            return format_html('{:.2f}', obj.target_value)
        return '-'
    target_value_display.short_description = 'Target'
    
    def status_display(self, obj):
        status_map = {
            'on_target': ('green', '✓ On Target'),
            'warning': ('orange', '⚠ Warning'),
            'critical': ('red', '✗ Critical'),
            'acceptable': ('blue', '• Acceptable'),
            'unknown': ('gray', '? Unknown'),
        }
        color, text = status_map.get(obj.status, ('gray', 'Unknown'))
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, text
        )
    status_display.short_description = 'Status'
    
    def last_updated(self, obj):
        latest = obj.values.order_by('-period_end').first()
        if latest:
            return latest.period_end.date()
        return 'Never'
    last_updated.short_description = 'Last Updated'
    
    def calculate_selected_kpis(self, request, queryset):
        """Calculate selected KPIs"""
        from .tasks import calculate_kpi_task
        
        for kpi in queryset:
            calculate_kpi_task.delay(kpi.slug)
        
        self.message_user(
            request,
            f'Scheduled calculation for {queryset.count()} KPIs.'
        )
    calculate_selected_kpis.short_description = "Calculate selected KPIs"
    
    def export_kpis_csv(self, request, queryset):
        """Export KPI data to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="kpis_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'KPI Name', 'Type', 'Current Value', 'Target Value',
            'Min Threshold', 'Max Threshold', 'Status', 'Calculation Period',
            'Last Updated', 'Is Active'
        ])
        
        for kpi in queryset:
            writer.writerow([
                kpi.name,
                kpi.get_kpi_type_display(),
                kpi.current_value or '',
                kpi.target_value or '',
                kpi.min_threshold or '',
                kpi.max_threshold or '',
                kpi.status,
                kpi.get_calculation_period_display(),
                kpi.last_updated,
                kpi.is_active
            ])
        
        return response
    export_kpis_csv.short_description = "Export selected KPIs to CSV"


@admin.register(KPIValue)
class KPIValueAdmin(admin.ModelAdmin):
    list_display = [
        'kpi_name', 'value_display', 'period_range',
        'data_points', 'calculated_at'
    ]
    list_filter = [
        ('period_end', admin.DateFieldListFilter),
        'kpi__kpi_type'
    ]
    search_fields = ['kpi__name', 'kpi__slug']
    readonly_fields = ['calculated_at']
    
    def kpi_name(self, obj):
        url = reverse('admin:analytics_kpi_change', args=[obj.kpi.id])
        return format_html('<a href="{}">{}</a>', url, obj.kpi.name)
    kpi_name.short_description = 'KPI'
    kpi_name.admin_order_field = 'kpi__name'
    
    def value_display(self, obj):
        if obj.kpi.kpi_type == 'financial':
            return format_html('<strong>${:,.2f}</strong>', obj.value)
        elif obj.kpi.kpi_type == 'quality':
            return format_html('<strong>{:.2f}</strong>', obj.value)
        else:
            return format_html('<strong>{:,.0f}</strong>', obj.value)
    value_display.short_description = 'Value'
    
    def period_range(self, obj):
        return f"{obj.period_start.date()} to {obj.period_end.date()}"
    period_range.short_description = 'Period'


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'slug', 'is_public', 'widget_count',
        'created_by', 'created_at'
    ]
    list_filter = ['is_public', 'is_active']
    search_fields = ['name', 'slug', 'description']
    filter_horizontal = ['accessible_by']
    readonly_fields = ['created_at', 'updated_at']
    
    def widget_count(self, obj):
        return obj.widgets.count()
    widget_count.short_description = 'Widgets'


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'dashboard', 'widget_type_display',
        'kpi_name', 'is_visible', 'sort_order'
    ]
    list_filter = ['widget_type', 'is_visible', 'dashboard']
    search_fields = ['title', 'dashboard__name']
    list_editable = ['sort_order', 'is_visible']
    
    def widget_type_display(self, obj):
        return obj.get_widget_type_display()
    widget_type_display.short_description = 'Type'
    
    def kpi_name(self, obj):
        if obj.kpi:
            url = reverse('admin:analytics_kpi_change', args=[obj.kpi.id])
            return format_html('<a href="{}">{}</a>', url, obj.kpi.name)
        return '-'
    kpi_name.short_description = 'KPI'


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'report_type_display', 'schedule_display',
        'last_generated', 'execution_count', 'is_active'
    ]
    list_filter = ['report_type', 'schedule', 'is_active']
    search_fields = ['name', 'slug', 'description']
    filter_horizontal = ['recipients', 'accessible_by']
    readonly_fields = [
        'last_generated_at', 'last_generated_by',
        'created_at', 'updated_at'
    ]
    actions = ['generate_reports', 'schedule_reports', 'export_reports_csv']
    
    def report_type_display(self, obj):
        return obj.get_report_type_display()
    report_type_display.short_description = 'Type'
    
    def schedule_display(self, obj):
        if obj.schedule == 'manual':
            return 'Manual Only'
        elif obj.schedule_time:
            return f"{obj.get_schedule_display()} at {obj.schedule_time}"
        return obj.get_schedule_display()
    schedule_display.short_description = 'Schedule'
    
    def last_generated(self, obj):
        if obj.last_generated_at:
            return obj.last_generated_at.strftime('%Y-%m-%d %H:%M')
        return 'Never'
    last_generated.short_description = 'Last Generated'
    
    def execution_count(self, obj):
        return obj.executions.count()
    execution_count.short_description = 'Executions'
    
    def generate_reports(self, request, queryset):
        """Generate selected reports"""
        from .tasks import generate_report_task
        
        for report in queryset:
            generate_report_task.delay(report.id, request.user.id)
        
        self.message_user(
            request,
            f'Scheduled generation for {queryset.count()} reports.'
        )
    generate_reports.short_description = "Generate selected reports"


@admin.register(ReportExecution)
class ReportExecutionAdmin(admin.ModelAdmin):
    list_display = [
        'report_name', 'status_display', 'output_format',
        'started_at', 'completed_at', 'duration',
        'triggered_by', 'triggered_from'
    ]
    list_filter = ['status', 'output_format', 'triggered_from']
    search_fields = ['report__name', 'error_message']
    readonly_fields = [
        'started_at', 'completed_at', 'duration_seconds',
        'error_message', 'logs', 'created_at'
    ]
    
    def report_name(self, obj):
        url = reverse('admin:analytics_report_change', args=[obj.report.id])
        return format_html('<a href="{}">{}</a>', url, obj.report.name)
    report_name.short_description = 'Report'
    
    def status_display(self, obj):
        color_map = {
            'completed': 'green',
            'running': 'blue',
            'pending': 'orange',
            'failed': 'red',
            'cancelled': 'gray',
        }
        color = color_map.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def duration(self, obj):
        if obj.duration_seconds:
            return f"{obj.duration_seconds:.1f}s"
        return '-'
    duration.short_description = 'Duration'
    
    def started_at(self, obj):
        if obj.started_at:
            return obj.started_at.strftime('%Y-%m-%d %H:%M:%S')
        return '-'
    started_at.short_description = 'Started'
    
    def completed_at(self, obj):
        if obj.completed_at:
            return obj.completed_at.strftime('%Y-%m-%d %H:%M:%S')
        return '-'
    completed_at.short_description = 'Completed'