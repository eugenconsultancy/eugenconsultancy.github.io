from celery import shared_task
from django.utils import timezone
from datetime import timedelta, datetime
import logging
import os
import tempfile

from .models.kpi import KPI, Report, ReportExecution
from .services.report_generator import AnalyticsService, ReportGeneratorService
from ..notifications.services import NotificationService

logger = logging.getLogger(__name__)


@shared_task
def calculate_kpi_task(kpi_slug, period_start=None, period_end=None):
    """Calculate KPI value"""
    try:
        from .services.report_generator import AnalyticsService
        
        # Set default periods if not provided
        if not period_end:
            period_end = timezone.now()
        
        # Determine period based on KPI settings
        try:
            kpi = KPI.objects.get(slug=kpi_slug)
            
            if not period_start:
                if kpi.calculation_period == 'daily':
                    period_start = period_end - timedelta(days=1)
                elif kpi.calculation_period == 'weekly':
                    period_start = period_end - timedelta(weeks=1)
                elif kpi.calculation_period == 'monthly':
                    period_start = period_end - timedelta(days=30)
                elif kpi.calculation_period == 'quarterly':
                    period_start = period_end - timedelta(days=90)
                else:
                    period_start = period_end - timedelta(days=1)
            
            kpi_value = AnalyticsService.calculate_kpi(kpi_slug, period_start, period_end)
            
            if kpi_value:
                logger.info(f"Calculated KPI {kpi_slug}: {kpi_value.value} for period {period_start} to {period_end}")
                return True
            else:
                logger.warning(f"No value calculated for KPI {kpi_slug}")
                return False
                
        except KPI.DoesNotExist:
            logger.error(f"KPI {kpi_slug} not found")
            return False
            
    except Exception as e:
        logger.error(f"Failed to calculate KPI {kpi_slug}: {str(e)}", exc_info=True)
        return False


@shared_task
def calculate_all_kpis_task():
    """Calculate all active KPIs"""
    try:
        kpis = KPI.objects.filter(is_active=True, is_auto_calculated=True)
        
        for kpi in kpis:
            calculate_kpi_task.delay(kpi.slug)
        
        logger.info(f"Scheduled calculation for {kpis.count()} KPIs")
        return True
    except Exception as e:
        logger.error(f"Failed to schedule KPI calculations: {str(e)}", exc_info=True)
        return False


@shared_task(bind=True)
def generate_report_task(self, execution_id):
    """Generate report asynchronously"""
    try:
        from .services.report_generator import AnalyticsService, ReportGeneratorService
        
        execution = ReportExecution.objects.get(id=execution_id)
        execution.mark_running()
        
        # Generate report based on type
        report = execution.report
        start_date = execution.filters.get('start_date')
        end_date = execution.filters.get('end_date')
        
        # Parse dates if they exist
        if start_date:
            try:
                start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                start_date = timezone.now() - timedelta(days=30)
        else:
            start_date = timezone.now() - timedelta(days=30)
            
        if end_date:
            try:
                end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                end_date = timezone.now()
        else:
            end_date = timezone.now()
        
        # Generate report data
        report_data = AnalyticsService.generate_performance_report(
            start_date,
            end_date
        )
        
        # Generate file based on format
        if execution.output_format == 'excel':
            try:
                excel_file = ReportGeneratorService.generate_excel_report(report_data)
                
                # Save file to temporary location
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                    tmp.write(excel_file.getvalue())
                    file_path = tmp.name
                
                file_size = os.path.getsize(file_path)
                
                execution.mark_completed(file_path=file_path, file_size=file_size)
                
            except Exception as e:
                logger.error(f"Failed to generate Excel report: {str(e)}", exc_info=True)
                raise
            
        elif execution.output_format == 'pdf':
            try:
                # Generate PDF report
                pdf_path = ReportGeneratorService.generate_pdf_report(report_data)
                file_size = os.path.getsize(pdf_path)
                
                execution.mark_completed(file_path=pdf_path, file_size=file_size)
                
            except Exception as e:
                logger.error(f"Failed to generate PDF report: {str(e)}", exc_info=True)
                raise
                
        elif execution.output_format == 'csv':
            try:
                # For CSV, we'll create a simple CSV file
                import csv
                import pandas as pd
                
                # Convert report data to DataFrame and then to CSV
                dataframes = AnalyticsService.export_to_dataframe(report_data)
                
                # Create a temporary CSV file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as tmp:
                    writer = csv.writer(tmp)
                    
                    # Write summary data
                    writer.writerow(['Report Summary'])
                    writer.writerow(['Metric', 'Value'])
                    for key, value in report_data.get('summary', {}).items():
                        writer.writerow([key.replace('_', ' ').title(), value])
                    
                    writer.writerow([])
                    writer.writerow(['Detailed Data'])
                    
                    # Write financial breakdown if available
                    if 'financial_breakdown' in report_data:
                        writer.writerow(['Financial Breakdown'])
                        writer.writerow(['Date', 'Order Count', 'Revenue', 'Avg Order Value'])
                        for item in report_data['financial_breakdown']:
                            writer.writerow([
                                item.get('date', ''),
                                item.get('order_count', 0),
                                item.get('revenue', 0),
                                item.get('avg_order_value', 0)
                            ])
                    
                    file_path = tmp.name
                
                file_size = os.path.getsize(file_path)
                execution.mark_completed(file_path=file_path, file_size=file_size)
                
            except Exception as e:
                logger.error(f"Failed to generate CSV report: {str(e)}", exc_info=True)
                raise
                
        else:
            raise ValueError(f"Unsupported output format: {execution.output_format}")
        
        # Notify user if requested
        if execution.triggered_by:
            try:
                NotificationService.notify_user(
                    user=execution.triggered_by,
                    subject=f"Report Generated: {report.name}",
                    message=f"Your report '{report.name}' has been generated successfully. You can download it from the reports section.",
                    notification_type='report_generated'
                )
            except Exception as e:
                logger.warning(f"Failed to send notification for report {execution.id}: {str(e)}")
        
        logger.info(f"Generated report {execution.id} for {report.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to generate report {execution_id}: {str(e)}", exc_info=True)
        if 'execution' in locals():
            execution.mark_failed(str(e))
        return False


@shared_task
def process_scheduled_reports():
    """Process scheduled reports"""
    try:
        now = timezone.now()
        reports = Report.objects.filter(
            is_active=True,
            schedule__in=['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
        )
        
        processed_count = 0
        
        for report in reports:
            try:
                # Check if it's time to run
                if report.schedule_time and now.time() < report.schedule_time:
                    continue
                
                # Check day of week/month
                should_run = False
                
                if report.schedule == 'daily':
                    should_run = True
                    
                elif report.schedule == 'weekly' and report.schedule_day is not None:
                    # schedule_day: 0=Monday, 6=Sunday
                    if now.weekday() == report.schedule_day:
                        should_run = True
                        
                elif report.schedule == 'monthly' and report.schedule_day is not None:
                    # schedule_day: day of month (1-31)
                    if now.day == report.schedule_day:
                        should_run = True
                        
                elif report.schedule == 'quarterly':
                    # Run on first day of quarter
                    quarter_start_month = ((now.month - 1) // 3) * 3 + 1
                    if now.month == quarter_start_month and now.day == 1:
                        should_run = True
                        
                elif report.schedule == 'yearly':
                    # Run on January 1st
                    if now.month == 1 and now.day == 1:
                        should_run = True
                
                if not should_run:
                    continue
                
                # Create execution record
                execution = ReportExecution.objects.create(
                    report=report,
                    output_format=report.default_format,
                    triggered_from='scheduled',
                    filters={
                        'start_date': (now - timedelta(days=30)).isoformat(),
                        'end_date': now.isoformat(),
                    }
                )
                
                # Schedule generation
                generate_report_task.delay(execution.id)
                processed_count += 1
                
                # Update last generated timestamp
                report.last_generated_at = now
                report.save(update_fields=['last_generated_at'])
                
            except Exception as e:
                logger.error(f"Failed to schedule report {report.id}: {str(e)}", exc_info=True)
                continue
        
        if processed_count > 0:
            logger.info(f"Processed {processed_count} scheduled reports")
        
        return processed_count > 0
        
    except Exception as e:
        logger.error(f"Failed to process scheduled reports: {str(e)}", exc_info=True)
        return False


@shared_task
def cleanup_old_reports(days=30):
    """Clean up old report files"""
    try:
        threshold = timezone.now() - timedelta(days=days)
        old_executions = ReportExecution.objects.filter(
            created_at__lt=threshold,
            file_path__isnull=False
        )
        
        cleaned = 0
        for execution in old_executions:
            try:
                if execution.file_path and os.path.exists(execution.file_path):
                    os.remove(execution.file_path)
                    execution.file_path = ''
                    execution.save(update_fields=['file_path'])
                    cleaned += 1
            except Exception as e:
                logger.warning(f"Failed to clean up report file {execution.file_path}: {str(e)}")
        
        logger.info(f"Cleaned up {cleaned} old report files")
        return cleaned
        
    except Exception as e:
        logger.error(f"Failed to clean up old reports: {str(e)}", exc_info=True)
        return 0


@shared_task
def send_kpi_alerts():
    """Send alerts for KPIs that are in warning or critical status"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        
        critical_kpis = []
        warning_kpis = []
        
        for kpi in KPI.objects.filter(is_active=True):
            if kpi.status == 'critical':
                critical_kpis.append(kpi)
            elif kpi.status == 'warning':
                warning_kpis.append(kpi)
        
        # Send alerts if there are critical KPIs
        if critical_kpis:
            subject = f"⚠️ CRITICAL: {len(critical_kpis)} KPIs Require Immediate Attention"
            message_lines = ["The following KPIs are in CRITICAL status:\n"]
            
            for kpi in critical_kpis:
                message_lines.append(f"- {kpi.name}: {kpi.current_value} (Target: {kpi.target_value})")
                message_lines.append(f"  Status: {kpi.status} | Last Updated: {kpi.values.first().calculated_at if kpi.values.exists() else 'Never'}")
                message_lines.append("")
            
            message = "\n".join(message_lines)
            
            # Send to admin users
            from django.contrib.auth.models import User
            admin_emails = User.objects.filter(
                is_staff=True,
                is_active=True
            ).values_list('email', flat=True)
            
            for email in admin_emails:
                try:
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                except Exception as e:
                    logger.error(f"Failed to send KPI alert to {email}: {str(e)}")
        
        # Log warning KPIs
        if warning_kpis:
            warning_names = [kpi.name for kpi in warning_kpis]
            logger.warning(f"Found {len(warning_kpis)} KPIs in warning status: {', '.join(warning_names)}")
        
        return len(critical_kpis) + len(warning_kpis)
        
    except Exception as e:
        logger.error(f"Failed to send KPI alerts: {str(e)}", exc_info=True)
        return 0


@shared_task
def generate_periodic_reports():
    """Generate standard periodic reports"""
    try:
        now = timezone.now()
        
        # Daily summary report
        daily_report, created = Report.objects.get_or_create(
            slug='daily-summary',
            defaults={
                'name': 'Daily Summary Report',
                'report_type': 'operational',
                'description': 'Automated daily summary of platform performance',
                'default_format': 'pdf',
                'schedule': 'daily',
                'schedule_time': timezone.now().replace(hour=23, minute=59, second=0).time(),
                'is_active': True,
            }
        )
        
        # Weekly performance report
        weekly_report, created = Report.objects.get_or_create(
            slug='weekly-performance',
            defaults={
                'name': 'Weekly Performance Report',
                'report_type': 'performance',
                'description': 'Weekly performance metrics and trends',
                'default_format': 'excel',
                'schedule': 'weekly',
                'schedule_day': 0,  # Monday
                'schedule_time': timezone.now().replace(hour=8, minute=0, second=0).time(),
                'is_active': True,
            }
        )
        
        # Monthly financial report
        monthly_report, created = Report.objects.get_or_create(
            slug='monthly-financial',
            defaults={
                'name': 'Monthly Financial Report',
                'report_type': 'financial',
                'description': 'Monthly financial summary and analysis',
                'default_format': 'excel',
                'schedule': 'monthly',
                'schedule_day': 1,  # 1st of month
                'schedule_time': timezone.now().replace(hour=9, minute=0, second=0).time(),
                'is_active': True,
            }
        )
        
        logger.info("Periodic reports configuration checked/updated")
        return True
        
    except Exception as e:
        logger.error(f"Failed to generate periodic reports: {str(e)}", exc_info=True)
        return False