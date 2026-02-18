import random
import string
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q

from accounts import models
from .models import Payment, StudentFee, FeeStructure
from .models import PaymentReceipt
from .models import AdditionalCharge
from django.db.models import Avg
models.Count


def generate_transaction_id():
    """
    Generate a unique transaction ID
    Format: TXN-YYYYMMDD-XXXXXX (where XXXXXX is random alphanumeric)
    """
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"TXN-{date_str}-{random_str}"

def generate_receipt_number():
    """
    Generate a unique receipt number
    Format: RCPT-YYYYMMDD-XXXXXX (where XXXXXX is sequential number based on count)
    """
    date_str = datetime.now().strftime('%Y%m%d')
    
    # Get count of receipts for today
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = PaymentReceipt.objects.filter(
        generated_at__gte=today_start
    ).count()
    
    sequential_num = str(today_count + 1).zfill(6)
    return f"RCPT-{date_str}-{sequential_num}"

def calculate_financial_summary(start_date=None, end_date=None):
    """
    Calculate financial summary for a given period
    """
    if not start_date:
        start_date = timezone.now().replace(day=1)  # Start of current month
    if not end_date:
        end_date = timezone.now()
    
    # Payment summary
    payments = Payment.objects.filter(
        payment_date__range=[start_date, end_date],
        status='completed'
    )
    
    total_payments = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Payment method breakdown
    payment_methods = payments.values('payment_method').annotate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    # Student fee summary
    student_fees = StudentFee.objects.all()
    
    total_due = student_fees.aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00')
    total_paid = student_fees.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    total_balance = student_fees.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    
    # Payment status breakdown
    payment_status = {
        'completed': payments.filter(status='completed').count(),
        'pending': Payment.objects.filter(status='pending').count(),
        'failed': Payment.objects.filter(status='failed').count(),
    }
    
    # Fee structure summary
    fee_structures = FeeStructure.objects.filter(is_active=True)
    
    return {
        'period': {
            'start_date': start_date,
            'end_date': end_date
        },
        'payments': {
            'total': total_payments,
            'count': payments.count(),
            'methods': list(payment_methods),
            'status': payment_status
        },
        'fees': {
            'total_due': total_due,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'collection_rate': (total_paid / total_due * 100) if total_due > 0 else 0,
            'student_count': student_fees.count(),
            'fully_paid': student_fees.filter(is_paid=True).count(),
            'partially_paid': student_fees.filter(is_paid=False, amount_paid__gt=0).count(),
            'not_paid': student_fees.filter(amount_paid=0).count(),
        },
        'fee_structures': {
            'active_count': fee_structures.count(),
            'total_fee_amount': sum(fs.total_fee for fs in fee_structures),
        }
    }

def send_payment_reminder(days_before=7):
    """
    Send payment reminders to students with upcoming due dates
    """
    today = timezone.now().date()
    reminder_date = today + timedelta(days=days_before)
    
    # Get student fees due on or before reminder date
    upcoming_fees = StudentFee.objects.filter(
        due_date__lte=reminder_date,
        due_date__gte=today,
        is_paid=False
    ).select_related('student__user')
    
    reminders = []
    
    for fee in upcoming_fees:
        reminder = {
            'student': fee.student,
            'fee_structure': fee.fee_structure,
            'due_date': fee.due_date,
            'balance': fee.balance,
            'days_until_due': (fee.due_date - today).days,
            'student_email': fee.student.user.email,
            'student_phone': fee.student.phone,
            'parent_phone': fee.student.parent_phone,
        }
        reminders.append(reminder)
    
    return reminders

def validate_mpesa_phone_number(phone_number):
    """
    Validate M-Pesa phone number format
    Expected format: 2547XXXXXXXX (12 digits starting with 254)
    """
    if not phone_number:
        return False
    
    # Remove any spaces or dashes
    phone = phone_number.strip().replace(' ', '').replace('-', '')
    
    # Check length and format
    if len(phone) != 12:
        return False
    
    if not phone.startswith('254'):
        return False
    
    # Check if the rest are digits
    if not phone[3:].isdigit():
        return False
    
    # Check if it starts with 2547 (Kenyan mobile)
    if not phone[3] == '7':
        return False
    
    return True

def format_currency(amount):
    """
    Format amount as currency string
    """
    if amount is None:
        return "Ksh 0.00"
    
    return f"Ksh {amount:,.2f}"

def get_student_financial_summary(student):
    """
    Get comprehensive financial summary for a student
    """
    # Get all student fees
    student_fees = StudentFee.objects.filter(student=student)
    
    # Get all payments
    payments = Payment.objects.filter(student=student).order_by('-payment_date')
    
    # Get additional charges
    additional_charges = AdditionalCharge.objects.filter(student=student, is_paid=False)
    
    # Calculate totals
    total_fees_assigned = student_fees.count()
    total_amount_due = student_fees.aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00')
    total_amount_paid = student_fees.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    total_balance = student_fees.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    
    # Get current active fee
    current_fee = student_fees.filter(fee_structure__is_active=True).first()
    
    # Calculate payment statistics
    payment_stats = {
        'total_payments': payments.count(),
        'total_paid': payments.filter(status='completed').aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'pending_payments': payments.filter(status='pending').count(),
        'last_payment_date': payments.filter(status='completed').first().payment_date if payments.filter(status='completed').exists() else None,
        'payment_methods': payments.values('payment_method').annotate(count=Count('id'), total=Sum('amount')),
    }
    
    # Calculate additional charges summary
    charges_summary = {
        'total_charges': additional_charges.count(),
        'total_amount': additional_charges.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
        'by_type': additional_charges.values('charge_type').annotate(count=Count('id'), total=Sum('amount')),
    }
    
    return {
        'student': student,
        'summary': {
            'total_fees_assigned': total_fees_assigned,
            'total_amount_due': total_amount_due,
            'total_amount_paid': total_amount_paid,
            'total_balance': total_balance,
            'payment_completion': (total_amount_paid / total_amount_due * 100) if total_amount_due > 0 else 0,
        },
        'current_fee': current_fee,
        'payment_stats': payment_stats,
        'charges_summary': charges_summary,
        'recent_payments': payments[:5],  # Last 5 payments
        'outstanding_charges': additional_charges,
    }

def calculate_payment_statistics(start_date=None, end_date=None):
    """
    Calculate detailed payment statistics for reporting
    """
    if not start_date:
        start_date = timezone.now() - timedelta(days=30)  # Last 30 days
    if not end_date:
        end_date = timezone.now()
    
    # Daily payment totals
    daily_payments = Payment.objects.filter(
        payment_date__date__range=[start_date.date(), end_date.date()],
        status='completed'
    ).extra({'date': "date(payment_date)"}).values('date').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('date')
    
    # Payment method distribution
    method_distribution = Payment.objects.filter(
        payment_date__range=[start_date, end_date],
        status='completed'
    ).values('payment_method').annotate(
        total=Sum('amount'),
        count=Count('id'),
        percentage=models.Count('id') * 100.0 / models.Count('id')
    )
    
    # Average payment amount
    avg_payment = Payment.objects.filter(
        payment_date__range=[start_date, end_date],
        status='completed'
    ).aggregate(avg=Avg('amount'))['avg'] or Decimal('0.00')
    
    # Largest payment
    largest_payment = Payment.objects.filter(
        payment_date__range=[start_date, end_date],
        status='completed'
    ).order_by('-amount').first()
    
    # Payment success rate
    total_attempts = Payment.objects.filter(
        payment_date__range=[start_date, end_date]
    ).count()
    
    successful_attempts = Payment.objects.filter(
        payment_date__range=[start_date, end_date],
        status='completed'
    ).count()
    
    success_rate = (successful_attempts / total_attempts * 100) if total_attempts > 0 else 0
    
    return {
        'period': {
            'start_date': start_date,
            'end_date': end_date,
            'days': (end_date.date() - start_date.date()).days
        },
        'daily_payments': list(daily_payments),
        'method_distribution': list(method_distribution),
        'statistics': {
            'average_payment': avg_payment,
            'largest_payment': largest_payment.amount if largest_payment else Decimal('0.00'),
            'largest_payment_student': largest_payment.student if largest_payment else None,
            'success_rate': success_rate,
            'total_attempts': total_attempts,
            'successful_attempts': successful_attempts,
            'failed_attempts': total_attempts - successful_attempts,
        }
    }