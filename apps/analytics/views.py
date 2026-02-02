import json
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import DetailView, ListView, TemplateView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.core.paginator import Paginator

# Local App Models & Services
from .models.kpi import KPI, KPIValue, Dashboard, DashboardWidget, Report, ReportExecution
from .services.report_generator import AnalyticsService, ReportGeneratorService

# External App Imports (Cross-App)
from apps.accounts.decorators import admin_required
from apps.compliance.models import DataRequest  # Imported from its new home


@method_decorator([login_required, admin_required], name='dispatch')
class AnalyticsDashboardView(TemplateView):
    """Main analytics dashboard"""
    template_name = 'analytics/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get default dashboard or create one
        dashboard, created = Dashboard.objects.get_or_create(
            slug='main',
            defaults={
                'name': 'Main Dashboard',
                'created_by': self.request.user,
                'is_public': True,
            }
        )
        
        # Get KPIs for dashboard
        kpis = KPI.objects.filter(is_active=True).order_by('kpi_type', 'name')
        
        # Organize KPIs by type
        kpis_by_type = {}
        for kpi in kpis:
            kpi_type = kpi.get_kpi_type_display()
            if kpi_type not in kpis_by_type:
                kpis_by_type[kpi_type] = []
            kpis_by_type[kpi_type].append(kpi)
        
        context.update({
            'dashboard': dashboard,
            'kpis_by_type': kpis_by_type,
            'recent_values': self._get_recent_kpi_values(),
            'time_periods': [
                ('today', 'Today'),
                ('yesterday', 'Yesterday'),
                ('7d', 'Last 7 Days'),
                ('30d', 'Last 30 Days'),
                ('90d', 'Last 90 Days'),
            ]
        })
        
        return context
    
    def _get_recent_kpi_values(self):
        """Get recent KPI values for display"""
        # Get values from last 7 days
        period_end = datetime.now()
        period_start = period_end - timedelta(days=7)
        
        values = KPIValue.objects.filter(
            period_end__range=(period_start, period_end)
        ).select_related('kpi').order_by('kpi__name', '-period_end')
        
        # Group by KPI
        recent_values = {}
        for value in values:
            if value.kpi_id not in recent_values:
                recent_values[value.kpi_id] = {
                    'kpi': value.kpi,
                    'values': []
                }
            recent_values[value.kpi_id]['values'].append(value)
        
        return recent_values.values()


@method_decorator([login_required, admin_required], name='dispatch')
class KPIListView(ListView):
    """List all KPIs"""
    model = KPI
    template_name = 'analytics/kpi_list.html'
    context_object_name = 'kpis'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = KPI.objects.filter(is_active=True).order_by('kpi_type', 'name')
        
        # Filter by type
        kpi_type = self.request.GET.get('type')
        if kpi_type:
            queryset = queryset.filter(kpi_type=kpi_type)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            # This would need more complex filtering based on actual status calculation
            pass
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['kpi_types'] = KPI.KPI_TYPES
        return context


@method_decorator([login_required, admin_required], name='dispatch')
class KPIDetailView(DetailView):
    """View KPI details and history"""
    model = KPI
    template_name = 'analytics/kpi_detail.html'
    context_object_name = 'kpi'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get historical values
        values = self.object.values.order_by('-period_end')[:100]
        
        # Get trend data
        trend_data = self._get_trend_data(values)
        
        context.update({
            'values': values,
            'trend_data': json.dumps(trend_data),
            'recent_periods': self._get_recent_periods(),
        })
        
        return context
    
    def _get_trend_data(self, values):
        """Prepare trend data for chart"""
        trend_data = {
            'labels': [],
            'datasets': [{
                'label': self.object.name,
                'data': [],
                'borderColor': '#4CAF50',
                'backgroundColor': 'rgba(76, 175, 80, 0.1)',
                'fill': True,
            }]
        }
        
        for value in reversed(values[:30]):  # Last 30 values
            trend_data['labels'].append(value.period_end.strftime('%Y-%m-%d'))
            trend_data['datasets'][0]['data'].append(float(value.value))
        
        return trend_data
    
    def _get_recent_periods(self):
        """Get recent periods for comparison"""
        periods = []
        now = datetime.now()
        
        for i in range(4):
            period_end = now - timedelta(days=i*7)  # Weekly periods
            period_start = period_end - timedelta(days=7)
            
            periods.append({
                'name': f"Week {i+1} ago",
                'start': period_start,
                'end': period_end,
            })
        
        return periods


@login_required
@admin_required
def calculate_kpi_api(request, kpi_slug):
    """API endpoint to calculate KPI"""
    try:
        period_end = datetime.now()
        
        # Determine period based on query params
        period = request.GET.get('period', 'daily')
        if period == 'daily':
            period_start = period_end - timedelta(days=1)
        elif period == 'weekly':
            period_start = period_end - timedelta(days=7)
        elif period == 'monthly':
            period_start = period_end - timedelta(days=30)
        else:
            period_start = period_end - timedelta(days=1)
        
        kpi_value = AnalyticsService.calculate_kpi(
            kpi_slug,
            period_start,
            period_end
        )
        
        if kpi_value:
            return JsonResponse({
                'success': True,
                'value': float(kpi_value.value),
                'period_start': kpi_value.period_start.isoformat(),
                'period_end': kpi_value.period_end.isoformat(),
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to calculate KPI'
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@method_decorator([login_required, admin_required], name='dispatch')
class ReportListView(ListView):
    """List all reports"""
    model = Report
    template_name = 'analytics/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Report.objects.filter(is_active=True).order_by('name')
        
        # Filter by type
        report_type = self.request.GET.get('type')
        if report_type:
            queryset = queryset.filter(report_type=report_type)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['report_types'] = Report.REPORT_TYPES
        return context


@method_decorator([login_required, admin_required], name='dispatch')
class ReportDetailView(DetailView):
    """View report details and history"""
    model = Report
    template_name = 'analytics/report_detail.html'
    context_object_name = 'report'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get execution history
        executions = self.object.executions.order_by('-created_at')[:20]
        
        context.update({
            'executions': executions,
            'formats': Report.FORMATS,
            'schedules': Report.SCHEDULES,
        })
        
        return context


@login_required
@admin_required
@require_http_methods(['POST'])
def generate_report_api(request, report_id):
    """API endpoint to generate report"""
    try:
        report = get_object_or_404(Report, id=report_id)
        
        # Create execution record
        execution = ReportExecution.objects.create(
            report=report,
            output_format=request.POST.get('format', report.default_format),
            triggered_by=request.user,
            triggered_from='web',
            parameters=json.loads(request.POST.get('parameters', '{}')),
            filters=json.loads(request.POST.get('filters', '{}')),
        )
        
        # Start generation (in background)
        from apps.analytics import tasks
        tasks.generate_report_task.delay()
        
        return JsonResponse({
            'success': True,
            'execution_id': str(execution.id),
            'message': 'Report generation started'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
@admin_required
def download_report(request, execution_id):
    """Download generated report"""
    execution = get_object_or_404(ReportExecution, id=execution_id)
    
    if not execution.is_successful or not execution.file_path:
        messages.error(request, 'Report not available for download.')
        return redirect('analytics:report_detail', pk=execution.report.id)
    
    # Serve file based on format
    # In production, this would serve from secure storage
    try:
        with open(execution.file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            filename = f"{execution.report.slug}_{execution.created_at.strftime('%Y%m%d_%H%M%S')}.{execution.output_format}"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    except FileNotFoundError:
        messages.error(request, 'Report file not found.')
        return redirect('analytics:report_detail', pk=execution.report.id)


@method_decorator([login_required, admin_required], name='dispatch')
class PerformanceReportView(TemplateView):
    """Interactive performance report view"""
    template_name = 'analytics/performance_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date range from query params
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        try:
            if 'start_date' in self.request.GET:
                start_date = datetime.strptime(self.request.GET['start_date'], '%Y-%m-%d')
            if 'end_date' in self.request.GET:
                end_date = datetime.strptime(self.request.GET['end_date'], '%Y-%m-%d')
        except ValueError:
            pass
        
        # Generate report data
        report_data = AnalyticsService.generate_performance_report(
            start_date,
            end_date
        )
        
        context.update({
            'report_data': report_data,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'date_ranges': [
                ('7d', 'Last 7 Days'),
                ('30d', 'Last 30 Days'),
                ('90d', 'Last 90 Days'),
                ('180d', 'Last 180 Days'),
                ('365d', 'Last Year'),
            ]
        })
        
        return context


@login_required
@admin_required
def export_performance_report(request):
    """Export performance report in various formats"""
    format_type = request.GET.get('format', 'excel')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        messages.error(request, 'Invalid date format.')
        return redirect('analytics:performance_report')
    
    # Generate report data
    report_data = AnalyticsService.generate_performance_report(start_date, end_date)
    
    if format_type == 'excel':
        try:
            excel_file = ReportGeneratorService.generate_excel_report(report_data)
            
            response = HttpResponse(
                excel_file.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f"performance_report_{start_date_str}_to_{end_date_str}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        except Exception as e:
            messages.error(request, f'Failed to generate Excel file: {str(e)}')
            return redirect('analytics:performance_report')
    
    elif format_type == 'csv':
        try:
            dataframes = AnalyticsService.export_to_dataframe(report_data)
            
            # For simplicity, export only the financial breakdown
            if 'financial_breakdown' in dataframes:
                df = dataframes['financial_breakdown']
                response = HttpResponse(content_type='text/csv')
                filename = f"financial_report_{start_date_str}_to_{end_date_str}.csv"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                df.to_csv(response, index=False)
                return response
            
            messages.error(request, 'No data available for export.')
            return redirect('analytics:performance_report')
            
        except Exception as e:
            messages.error(request, f'Failed to generate CSV file: {str(e)}')
            return redirect('analytics:performance_report')
    
    else:
        messages.error(request, 'Unsupported export format.')
        return redirect('analytics:performance_report')