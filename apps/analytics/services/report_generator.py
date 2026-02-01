import logging
import pandas as pd
from datetime import datetime, timedelta
from django.db import connection
from django.db.models import (
    Count, Sum, Avg, F, Q, Case, When, Value, FloatField,
    ExpressionWrapper, DurationField
)
from django.utils import timezone
from django.template.loader import render_to_string
from decimal import Decimal
import json

from apps.orders.models import Order
from apps.accounts.models import User, WriterProfile
from apps.payments.models import Payment
from apps.wallet.models import Wallet, Transaction
from apps.reviews.models import Review, WriterRatingSummary

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for generating analytics and reports"""
    
    @staticmethod
    def calculate_kpi(kpi_slug, period_start=None, period_end=None):
        """Calculate value for a specific KPI"""
        from ..models.kpi import KPI, KPIValue
        
        try:
            kpi = KPI.objects.get(slug=kpi_slug, is_active=True)
            
            # Set default period if not provided
            if not period_end:
                period_end = timezone.now()
            if not period_start:
                if kpi.calculation_period == 'daily':
                    period_start = period_end - timedelta(days=1)
                elif kpi.calculation_period == 'weekly':
                    period_start = period_end - timedelta(weeks=1)
                elif kpi.calculation_period == 'monthly':
                    period_start = period_end - timedelta(days=30)
            
            # Calculate based on KPI slug
            value = AnalyticsService._calculate_kpi_value(kpi, period_start, period_end)
            
            if value is not None:
                # Create or update KPI value
                kpi_value, created = KPIValue.objects.update_or_create(
                    kpi=kpi,
                    period_start=period_start,
                    period_end=period_end,
                    defaults={
                        'value': value,
                        'context_data': AnalyticsService._get_kpi_context(kpi, period_start, period_end)
                    }
                )
                
                logger.info(f"Calculated KPI {kpi_slug}: {value} for period {period_start} to {period_end}")
                return kpi_value
            
            return None
            
        except KPI.DoesNotExist:
            logger.error(f"KPI {kpi_slug} not found")
            return None
        except Exception as e:
            logger.error(f"Failed to calculate KPI {kpi_slug}: {str(e)}")
            return None
    
    @staticmethod
    def _calculate_kpi_value(kpi, period_start, period_end):
        """Calculate specific KPI values"""
        # Financial KPIs
        if kpi.slug == 'total_revenue':
            return AnalyticsService._calculate_total_revenue(period_start, period_end)
        elif kpi.slug == 'writer_payouts':
            return AnalyticsService._calculate_writer_payouts(period_start, period_end)
        elif kpi.slug == 'platform_revenue':
            return AnalyticsService._calculate_platform_revenue(period_start, period_end)
        elif kpi.slug == 'average_order_value':
            return AnalyticsService._calculate_average_order_value(period_start, period_end)
        
        # Operational KPIs
        elif kpi.slug == 'total_orders':
            return AnalyticsService._calculate_total_orders(period_start, period_end)
        elif kpi.slug == 'order_completion_rate':
            return AnalyticsService._calculate_order_completion_rate(period_start, period_end)
        elif kpi.slug == 'average_completion_time':
            return AnalyticsService._calculate_average_completion_time(period_start, period_end)
        
        # Quality KPIs
        elif kpi.slug == 'average_rating':
            return AnalyticsService._calculate_average_rating(period_start, period_end)
        elif kpi.slug == 'customer_satisfaction':
            return AnalyticsService._calculate_customer_satisfaction(period_start, period_end)
        elif kpi.slug == 'revision_rate':
            return AnalyticsService._calculate_revision_rate(period_start, period_end)
        
        # Writer KPIs
        elif kpi.slug == 'active_writers':
            return AnalyticsService._calculate_active_writers(period_start, period_end)
        elif kpi.slug == 'writer_approval_rate':
            return AnalyticsService._calculate_writer_approval_rate(period_start, period_end)
        elif kpi.slug == 'writer_retention_rate':
            return AnalyticsService._calculate_writer_retention_rate(period_start, period_end)
        
        # Customer KPIs
        elif kpi.slug == 'customer_acquisition':
            return AnalyticsService._calculate_customer_acquisition(period_start, period_end)
        elif kpi.slug == 'customer_retention':
            return AnalyticsService._calculate_customer_retention(period_start, period_end)
        elif kpi.slug == 'repeat_customer_rate':
            return AnalyticsService._calculate_repeat_customer_rate(period_start, period_end)
        
        return None
    
    @staticmethod
    def _calculate_total_revenue(period_start, period_end):
        """Calculate total revenue"""
        payments = Payment.objects.filter(
            status='released_to_wallet',
            released_at__range=(period_start, period_end)
        )
        total = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        return float(total)
    
    @staticmethod
    def _calculate_writer_payouts(period_start, period_end):
        """Calculate total writer payouts"""
        transactions = Transaction.objects.filter(
            transaction_type='debit',
            status='completed',
            created_at__range=(period_start, period_end)
        )
        total = transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        return float(total)
    
    @staticmethod
    def _calculate_platform_revenue(period_start, period_end):
        """Calculate platform revenue (revenue - payouts)"""
        revenue = AnalyticsService._calculate_total_revenue(period_start, period_end)
        payouts = AnalyticsService._calculate_writer_payouts(period_start, period_end)
        return revenue - payouts
    
    @staticmethod
    def _calculate_average_order_value(period_start, period_end):
        """Calculate average order value"""
        orders = Order.objects.filter(
            created_at__range=(period_start, period_end),
            status='completed'
        )
        if orders.exists():
            avg = orders.aggregate(avg=Avg('total_price'))['avg'] or Decimal('0.00')
            return float(avg)
        return 0.0
    
    @staticmethod
    def _calculate_total_orders(period_start, period_end):
        """Calculate total orders"""
        return Order.objects.filter(
            created_at__range=(period_start, period_end)
        ).count()
    
    @staticmethod
    def _calculate_order_completion_rate(period_start, period_end):
        """Calculate order completion rate"""
        total_orders = Order.objects.filter(
            created_at__range=(period_start, period_end)
        ).count()
        
        completed_orders = Order.objects.filter(
            created_at__range=(period_start, period_end),
            status='completed'
        ).count()
        
        if total_orders > 0:
            return (completed_orders / total_orders) * 100
        return 0.0
    
    @staticmethod
    def _calculate_average_completion_time(period_start, period_end):
        """Calculate average order completion time in hours"""
        completed_orders = Order.objects.filter(
            created_at__range=(period_start, period_end),
            status='completed',
            completed_at__isnull=False
        ).annotate(
            completion_time=ExpressionWrapper(
                F('completed_at') - F('created_at'),
                output_field=DurationField()
            )
        )
        
        if completed_orders.exists():
            avg_seconds = completed_orders.aggregate(
                avg=Avg('completion_time')
            )['avg'].total_seconds()
            return avg_seconds / 3600  # Convert to hours
        return 0.0
    
    @staticmethod
    def _calculate_average_rating(period_start, period_end):
        """Calculate average review rating"""
        reviews = Review.objects.filter(
            created_at__range=(period_start, period_end),
            is_approved=True,
            is_active=True
        )
        if reviews.exists():
            avg = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
            return float(avg)
        return 0.0
    
    @staticmethod
    def _calculate_customer_satisfaction(period_start, period_end):
        """Calculate customer satisfaction (percentage of 4-5 star reviews)"""
        reviews = Review.objects.filter(
            created_at__range=(period_start, period_end),
            is_approved=True,
            is_active=True
        )
        
        if reviews.exists():
            positive_reviews = reviews.filter(rating__gte=4).count()
            return (positive_reviews / reviews.count()) * 100
        return 0.0
    
    @staticmethod
    def _calculate_revision_rate(period_start, period_end):
        """Calculate revision rate"""
        completed_orders = Order.objects.filter(
            created_at__range=(period_start, period_end),
            status='completed'
        )
        
        if completed_orders.exists():
            revised_orders = completed_orders.filter(
                revisions__isnull=False
            ).distinct().count()
            return (revised_orders / completed_orders.count()) * 100
        return 0.0
    
    @staticmethod
    def _calculate_active_writers(period_start, period_end):
        """Calculate number of active writers"""
        return WriterProfile.objects.filter(
            verification_status='approved',
            user__orders_as_writer__created_at__range=(period_start, period_end)
        ).distinct().count()
    
    @staticmethod
    def _calculate_writer_approval_rate(period_start, period_end):
        """Calculate writer approval rate"""
        total_applications = WriterProfile.objects.filter(
            created_at__range=(period_start, period_end)
        ).count()
        
        approved_writers = WriterProfile.objects.filter(
            created_at__range=(period_start, period_end),
            verification_status='approved'
        ).count()
        
        if total_applications > 0:
            return (approved_writers / total_applications) * 100
        return 0.0
    
    @staticmethod
    def _calculate_writer_retention_rate(period_start, period_end):
        """Calculate writer retention rate"""
        # This is a simplified calculation
        active_period = period_end - timedelta(days=90)  # 3 months
        
        writers_start = WriterProfile.objects.filter(
            created_at__lte=active_period,
            verification_status='approved'
        ).count()
        
        writers_active = WriterProfile.objects.filter(
            created_at__lte=active_period,
            verification_status='approved',
            user__orders_as_writer__created_at__range=(period_start, period_end)
        ).distinct().count()
        
        if writers_start > 0:
            return (writers_active / writers_start) * 100
        return 0.0
    
    @staticmethod
    def _calculate_customer_acquisition(period_start, period_end):
        """Calculate new customer acquisition"""
        return User.objects.filter(
            role='customer',
            date_joined__range=(period_start, period_end)
        ).count()
    
    @staticmethod
    def _calculate_customer_retention(period_start, period_end):
        """Calculate customer retention rate"""
        # Customers who placed orders in previous period and current period
        previous_period_start = period_start - (period_end - period_start)
        
        repeat_customers = User.objects.filter(
            role='customer',
            orders_as_customer__created_at__range=(previous_period_start, period_start),
        ).distinct().count()
        
        previous_customers = User.objects.filter(
            role='customer',
            orders_as_customer__created_at__range=(previous_period_start, period_start)
        ).distinct().count()
        
        if previous_customers > 0:
            return (repeat_customers / previous_customers) * 100
        return 0.0
    
    @staticmethod
    def _calculate_repeat_customer_rate(period_start, period_end):
        """Calculate repeat customer rate"""
        all_customers = User.objects.filter(
            role='customer',
            orders_as_customer__created_at__range=(period_start, period_end)
        ).distinct().count()
        
        repeat_customers = User.objects.filter(
            role='customer',
            orders_as_customer__created_at__range=(period_start, period_end)
        ).annotate(order_count=Count('orders_as_customer')).filter(
            order_count__gt=1
        ).count()
        
        if all_customers > 0:
            return (repeat_customers / all_customers) * 100
        return 0.0
    
    @staticmethod
    def _get_kpi_context(kpi, period_start, period_end):
        """Get additional context for KPI"""
        context = {
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'calculated_at': timezone.now().isoformat(),
        }
        
        # Add specific context based on KPI type
        if kpi.kpi_type == 'financial':
            context.update({
                'currency': 'USD',
                'display_format': 'currency'
            })
        elif kpi.kpi_type == 'quality':
            context.update({
                'scale': '1-5',
                'display_format': 'rating'
            })
        
        return context
    
    @staticmethod
    def generate_performance_report(start_date, end_date, report_type='overall'):
        """Generate comprehensive performance report"""
        
        report_data = {
            'period': {
                'start': start_date,
                'end': end_date,
            },
            'summary': {
                'total_orders': AnalyticsService._calculate_total_orders(start_date, end_date),
                'total_revenue': AnalyticsService._calculate_total_revenue(start_date, end_date),
                'platform_revenue': AnalyticsService._calculate_platform_revenue(start_date, end_date),
                'order_completion_rate': AnalyticsService._calculate_order_completion_rate(start_date, end_date),
                'average_rating': AnalyticsService._calculate_average_rating(start_date, end_date),
            },
            'financial_breakdown': AnalyticsService._get_financial_breakdown(start_date, end_date),
            'order_metrics': AnalyticsService._get_order_metrics(start_date, end_date),
            'writer_performance': AnalyticsService._get_writer_performance(start_date, end_date),
            'customer_analysis': AnalyticsService._get_customer_analysis(start_date, end_date),
            'quality_metrics': AnalyticsService._get_quality_metrics(start_date, end_date),
        }
        
        return report_data
    
    @staticmethod
    def _get_financial_breakdown(start_date, end_date):
        """Get detailed financial breakdown"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as order_count,
                    SUM(total_price) as revenue,
                    AVG(total_price) as avg_order_value
                FROM orders_order
                WHERE created_at BETWEEN %s AND %s
                    AND status = 'completed'
                GROUP BY DATE(created_at)
                ORDER BY date
            """, [start_date, end_date])
            
            rows = cursor.fetchall()
            return [
                {
                    'date': row[0],
                    'order_count': row[1],
                    'revenue': float(row[2]) if row[2] else 0.0,
                    'avg_order_value': float(row[3]) if row[3] else 0.0,
                }
                for row in rows
            ]
    
    @staticmethod
    def _get_order_metrics(start_date, end_date):
        """Get detailed order metrics"""
        orders = Order.objects.filter(
            created_at__range=(start_date, end_date)
        )
        
        status_distribution = orders.values('status').annotate(
            count=Count('id'),
            percentage=Count('id') * 100.0 / orders.count()
        ).order_by('-count')
        
        subject_distribution = orders.values('subject').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return {
            'status_distribution': list(status_distribution),
            'subject_distribution': list(subject_distribution),
            'total_orders': orders.count(),
            'completed_orders': orders.filter(status='completed').count(),
            'cancelled_orders': orders.filter(status='cancelled').count(),
        }
    
    @staticmethod
    def _get_writer_performance(start_date, end_date):
        """Get writer performance metrics"""
        top_writers = WriterRatingSummary.objects.filter(
            writer__orders_as_writer__created_at__range=(start_date, end_date)
        ).select_related('writer').order_by('-average_rating')[:10]
        
        writer_metrics = []
        for summary in top_writers:
            writer_orders = Order.objects.filter(
                writer=summary.writer,
                created_at__range=(start_date, end_date)
            )
            
            completed_orders = writer_orders.filter(status='completed').count()
            total_orders = writer_orders.count()
            
            writer_metrics.append({
                'writer': summary.writer.email,
                'average_rating': float(summary.average_rating),
                'total_reviews': summary.total_reviews,
                'completed_orders': completed_orders,
                'completion_rate': (completed_orders / total_orders * 100) if total_orders > 0 else 0,
                'total_earned': float(summary.writer.wallet.total_earned) if hasattr(summary.writer, 'wallet') else 0,
            })
        
        return writer_metrics
    
    @staticmethod
    def _get_customer_analysis(start_date, end_date):
        """Get customer analysis"""
        customers = User.objects.filter(
            role='customer',
            orders_as_customer__created_at__range=(start_date, end_date)
        ).annotate(
            order_count=Count('orders_as_customer'),
            total_spent=Sum('orders_as_customer__total_price')
        ).order_by('-total_spent')[:10]
        
        return [
            {
                'customer': customer.email,
                'order_count': customer.order_count,
                'total_spent': float(customer.total_spent) if customer.total_spent else 0.0,
                'first_order': customer.orders_as_customer.order_by('created_at').first().created_at if customer.orders_as_customer.exists() else None,
            }
            for customer in customers
        ]
    
    @staticmethod
    def _get_quality_metrics(start_date, end_date):
        """Get quality metrics"""
        reviews = Review.objects.filter(
            created_at__range=(start_date, end_date),
            is_approved=True,
            is_active=True
        )
        
        if reviews.exists():
            rating_distribution = reviews.values('rating').annotate(
                count=Count('id'),
                percentage=Count('id') * 100.0 / reviews.count()
            ).order_by('rating')
            
            avg_metrics = reviews.aggregate(
                avg_communication=Avg('communication_rating'),
                avg_timeliness=Avg('timeliness_rating'),
                avg_quality=Avg('quality_rating'),
                avg_adherence=Avg('adherence_rating'),
            )
            
            return {
                'total_reviews': reviews.count(),
                'average_rating': reviews.aggregate(avg=Avg('rating'))['avg'] or 0,
                'rating_distribution': list(rating_distribution),
                'average_metrics': {
                    'communication': float(avg_metrics['avg_communication'] or 0),
                    'timeliness': float(avg_metrics['avg_timeliness'] or 0),
                    'quality': float(avg_metrics['avg_quality'] or 0),
                    'adherence': float(avg_metrics['avg_adherence'] or 0),
                },
                'positive_review_percentage': reviews.filter(rating__gte=4).count() / reviews.count() * 100,
            }
        
        return {}
    
    @staticmethod
    def export_to_dataframe(report_data):
        """Convert report data to pandas DataFrame for Excel/CSV export"""
        dataframes = {}
        
        # Financial data
        if 'financial_breakdown' in report_data:
            df_financial = pd.DataFrame(report_data['financial_breakdown'])
            dataframes['financial_breakdown'] = df_financial
        
        # Order metrics
        if 'order_metrics' in report_data:
            order_data = report_data['order_metrics']
            
            # Status distribution
            if 'status_distribution' in order_data:
                df_status = pd.DataFrame(order_data['status_distribution'])
                dataframes['order_status_distribution'] = df_status
            
            # Subject distribution
            if 'subject_distribution' in order_data:
                df_subject = pd.DataFrame(order_data['subject_distribution'])
                dataframes['subject_distribution'] = df_subject
        
        # Writer performance
        if 'writer_performance' in report_data:
            df_writers = pd.DataFrame(report_data['writer_performance'])
            dataframes['writer_performance'] = df_writers
        
        # Customer analysis
        if 'customer_analysis' in report_data:
            df_customers = pd.DataFrame(report_data['customer_analysis'])
            dataframes['customer_analysis'] = df_customers
        
        return dataframes


class ReportGeneratorService:
    """Service for generating formatted reports"""
    
    @staticmethod
    def generate_pdf_report(report_data, template_name='analytics/report_template.html'):
        """Generate PDF report from template"""
        from weasyprint import HTML
        from django.conf import settings
        import os
        
        try:
            # Render HTML template
            html_string = render_to_string(template_name, {
                'report': report_data,
                'generated_at': timezone.now(),
            })
            
            # Generate PDF
            pdf_file = HTML(string=html_string).write_pdf()
            
            # Save to temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(pdf_file)
                temp_path = tmp.name
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to generate PDF report: {str(e)}")
            raise
    
    @staticmethod
    def generate_excel_report(report_data):
        """Generate Excel report"""
        import pandas as pd
        from io import BytesIO
        
        try:
            # Get dataframes
            dataframes = AnalyticsService.export_to_dataframe(report_data)
            
            # Create Excel writer
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Write summary sheet
                summary_data = {
                    'Metric': [
                        'Total Orders',
                        'Total Revenue',
                        'Platform Revenue',
                        'Order Completion Rate',
                        'Average Rating',
                    ],
                    'Value': [
                        report_data['summary']['total_orders'],
                        f"${report_data['summary']['total_revenue']:,.2f}",
                        f"${report_data['summary']['platform_revenue']:,.2f}",
                        f"{report_data['summary']['order_completion_rate']:.1f}%",
                        f"{report_data['summary']['average_rating']:.2f}",
                    ]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
                
                # Write other sheets
                for sheet_name, df in dataframes.items():
                    df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Failed to generate Excel report: {str(e)}")
            raise