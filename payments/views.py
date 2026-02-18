from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages  # Change from school_messages to messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Q, Count
from django.utils import timezone
import json
from datetime import datetime, timedelta

from .models import FeeStructure, StudentFee, AdditionalCharge, Payment, PaymentReceipt
from .forms import (
    FeeStructureForm, StudentFeeForm, AdditionalChargeForm, 
    MpesaPaymentForm, PaymentForm
)
from .mpesa import MpesaAPI
from students.models import Student
from accounts.models import User

def is_admin(user):
    return user.is_authenticated and user.is_admin()

def is_student(user):
    return user.is_authenticated and user.is_student()

def is_teacher(user):
    return user.is_authenticated and user.is_teacher()

# ===== Admin Views =====

@login_required
@user_passes_test(is_admin)
def fee_structure_list(request):
    fee_structures = FeeStructure.objects.all()
    return render(request, 'payments/fee_structure_list.html', {'fee_structures': fee_structures})

@login_required
@user_passes_test(is_admin)
def fee_structure_create(request):
    if request.method == 'POST':
        form = FeeStructureForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fee structure created successfully!')
            return redirect('fee_structure_list')
    else:
        form = FeeStructureForm()
    return render(request, 'payments/fee_structure_form.html', {'form': form, 'title': 'Create Fee Structure'})

@login_required
@user_passes_test(is_admin)
def fee_structure_update(request, pk):
    fee_structure = get_object_or_404(FeeStructure, pk=pk)
    if request.method == 'POST':
        form = FeeStructureForm(request.POST, instance=fee_structure)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fee structure updated successfully!')
            return redirect('fee_structure_list')
    else:
        form = FeeStructureForm(instance=fee_structure)
    return render(request, 'payments/fee_structure_form.html', {'form': form, 'title': 'Update Fee Structure'})

@login_required
@user_passes_test(is_admin)
def student_fee_list(request):
    student_fees = StudentFee.objects.all()
    total_due = student_fees.aggregate(Sum('amount_due'))['amount_due__sum'] or 0
    total_paid = student_fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
    total_balance = student_fees.aggregate(Sum('balance'))['balance__sum'] or 0
    
    return render(request, 'payments/student_fee_list.html', {
        'student_fees': student_fees,
        'total_due': total_due,
        'total_paid': total_paid,
        'total_balance': total_balance,
    })

@login_required
@user_passes_test(is_admin)
def assign_fee_to_student(request):
    if request.method == 'POST':
        form = StudentFeeForm(request.POST)
        if form.is_valid():
            student_fee = form.save(commit=False)
            
            # Check if student already has this fee structure
            existing = StudentFee.objects.filter(
                student=student_fee.student,
                fee_structure=student_fee.fee_structure
            ).first()
            
            if existing:
                messages.warning(request, 'This student already has this fee structure assigned.')
                return redirect('student_fee_list')
            
            student_fee.save()
            
            # Create initial payment record if any amount is paid
            if request.POST.get('initial_payment'):
                try:
                    initial_amount = float(request.POST.get('initial_payment'))
                    if initial_amount > 0:
                        Payment.objects.create(
                            student_fee=student_fee,
                            student=student_fee.student,
                            amount=initial_amount,
                            payment_method='cash',
                            status='completed',
                            confirmed_by=request.user,
                            confirmed_at=timezone.now(),
                            description='Initial payment'
                        )
                        student_fee.amount_paid = initial_amount
                        student_fee.save()
                except ValueError:
                    pass
            
            messages.success(request, f'Fee assigned to {student_fee.student} successfully!')
            return redirect('student_fee_list')
    else:
        form = StudentFeeForm()
    
    return render(request, 'payments/assign_fee_form.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def add_additional_charge(request):
    if request.method == 'POST':
        form = AdditionalChargeForm(request.POST)
        if form.is_valid():
            charge = form.save(commit=False)
            charge.added_by = request.user
            charge.save()
            
            # Update student's fee balance
            try:
                student_fee = StudentFee.objects.filter(
                    student=charge.student,
                    fee_structure__is_active=True
                ).latest('created_at')
                
                student_fee.additional_charges += charge.amount
                student_fee.save()
                
                messages.success(request, f'Additional charge added to {charge.student} successfully!')
                
            except StudentFee.DoesNotExist:
                messages.warning(request, 'No active fee structure found for this student.')
            
            return redirect('student_fee_list')
    else:
        form = AdditionalChargeForm()
    
    return render(request, 'payments/additional_charge_form.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def record_payment(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST, user=request.user)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.status = 'completed'
            payment.confirmed_by = request.user
            payment.confirmed_at = timezone.now()
            payment.save()
            
            # Update student fee balance
            student_fee = payment.student_fee
            student_fee.amount_paid += payment.amount
            student_fee.save()
            
            # Generate receipt
            PaymentReceipt.objects.create(payment=payment)
            
            messages.success(request, f'Payment of {payment.amount} recorded successfully!')
            return redirect('payment_list')
    else:
        form = PaymentForm(user=request.user)
    
    return render(request, 'payments/record_payment_form.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def payment_list(request):
    payments = Payment.objects.all()
    return render(request, 'payments/payment_list.html', {'payments': payments})

# ===== Student Views =====

@login_required
@user_passes_test(is_student)
def student_financial_dashboard(request):
    try:
        student = Student.objects.get(user=request.user)
        
        # Get current fee
        current_fee = StudentFee.objects.filter(
            student=student,
            fee_structure__is_active=True
        ).first()
        
        # Get all student fees
        all_fees = StudentFee.objects.filter(student=student)
        
        # Get payments
        payments = Payment.objects.filter(student=student).order_by('-payment_date')
        
        # Get additional charges
        additional_charges = AdditionalCharge.objects.filter(
            student=student,
            is_paid=False
        )
        
        # Calculate statistics
        total_due = all_fees.aggregate(Sum('amount_due'))['amount_due__sum'] or 0
        total_paid = all_fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        total_balance = all_fees.aggregate(Sum('balance'))['balance__sum'] or 0
        
        # Get recent payments (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_payments = payments.filter(payment_date__gte=thirty_days_ago)
        
        return render(request, 'payments/student_financial_dashboard.html', {
            'student': student,
            'current_fee': current_fee,
            'all_fees': all_fees,
            'payments': payments,
            'additional_charges': additional_charges,
            'total_due': total_due,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'recent_payments': recent_payments,
        })
        
    except Student.DoesNotExist:
        messages.error(request, 'Student profile not found.')
        return redirect('dashboard')

@login_required
@user_passes_test(is_student)
def make_payment(request):
    try:
        student = Student.objects.get(user=request.user)
        
        # Get current fee
        current_fee = StudentFee.objects.filter(
            student=student,
            fee_structure__is_active=True
        ).first()
        
        if not current_fee:
            messages.error(request, 'No active fee structure found.')
            return redirect('student_financial_dashboard')
        
        if request.method == 'POST':
            form = MpesaPaymentForm(request.POST)
            if form.is_valid():
                phone_number = form.cleaned_data['phone_number']
                amount = form.cleaned_data['amount']
                description = form.cleaned_data['description']
                
                # Validate amount
                if amount > current_fee.balance:
                    messages.error(request, f'Amount cannot exceed balance of {current_fee.balance}.')
                    return redirect('make_payment')
                
                # Initialize M-Pesa API
                mpesa = MpesaAPI()
                
                # Generate account reference
                account_reference = f"{student.admission_number}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # Initiate STK Push
                result = mpesa.stk_push(
                    phone_number=phone_number,
                    amount=amount,
                    account_reference=account_reference,
                    transaction_desc=f"School fees payment - {student.user.get_full_name()}"
                )
                
                if result['success']:
                    # Create pending payment record
                    payment = Payment.objects.create(
                        student_fee=current_fee,
                        student=student,
                        amount=amount,
                        payment_method='mpesa',
                        phone_number=phone_number,
                        status='pending',
                        transaction_id=result.get('checkout_request_id', ''),
                        description=description,
                    )
                    
                    messages.success(
                        request, 
                        f'Payment request sent to {phone_number}. '
                        f'Please check your phone to complete the payment.'
                    )
                    return redirect('payment_status', payment_id=payment.id)
                else:
                    messages.error(request, f'Payment initiation failed: {result.get("error", "Unknown error")}')
            
        else:
            form = MpesaPaymentForm()
        
        return render(request, 'payments/make_payment.html', {
            'form': form,
            'current_fee': current_fee,
            'student': student,
        })
        
    except Student.DoesNotExist:
        messages.error(request, 'Student profile not found.')
        return redirect('dashboard')

@login_required
@user_passes_test(is_student)
def payment_status(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id, student__user=request.user)
    
    # Check payment status
    if payment.status == 'pending' and payment.transaction_id:
        mpesa = MpesaAPI()
        result = mpesa.check_transaction_status(payment.transaction_id)
        
        if result['success'] and result['data'].get('ResultCode') == '0':
            payment.status = 'completed'
            payment.mpesa_code = result['data'].get('MpesaReceiptNumber')
            payment.receipt_number = result['data'].get('MpesaReceiptNumber')
            payment.save()
            
            # Update student fee
            student_fee = payment.student_fee
            student_fee.amount_paid += payment.amount
            student_fee.save()
            
            # Generate receipt
            PaymentReceipt.objects.create(payment=payment)
    
    return render(request, 'payments/payment_status.html', {
        'payment': payment,
        'student': payment.student,
    })

@login_required
@user_passes_test(is_student)
def payment_history(request):
    try:
        student = Student.objects.get(user=request.user)
        payments = Payment.objects.filter(student=student).order_by('-payment_date')
        
        return render(request, 'payments/payment_history.html', {
            'payments': payments,
            'student': student,
        })
        
    except Student.DoesNotExist:
        messages.error(request, 'Student profile not found.')
        return redirect('dashboard')

# ===== M-Pesa Callback View =====

@csrf_exempt
def mpesa_callback(request):
    """Handle M-Pesa callback"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            callback_data = data.get('Body', {}).get('stkCallback', {})
            
            checkout_request_id = callback_data.get('CheckoutRequestID')
            result_code = callback_data.get('ResultCode')
            result_desc = callback_data.get('ResultDesc')
            
            # Find the payment
            payment = Payment.objects.filter(
                transaction_id=checkout_request_id,
                status='pending'
            ).first()
            
            if payment:
                if result_code == '0':
                    # Payment successful
                    payment.status = 'completed'
                    payment.mpesa_code = callback_data.get('CallbackMetadata', {}).get('Item', [{}])[1].get('Value', '')
                    payment.receipt_number = callback_data.get('CallbackMetadata', {}).get('Item', [{}])[1].get('Value', '')
                    
                    # Update student fee
                    student_fee = payment.student_fee
                    student_fee.amount_paid += payment.amount
                    student_fee.save()
                    
                    # Generate receipt
                    PaymentReceipt.objects.create(payment=payment)
                    
                else:
                    # Payment failed
                    payment.status = 'failed'
                    payment.description = result_desc
                
                payment.save()
            
            return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})
            
        except Exception as e:
            return JsonResponse({'ResultCode': 1, 'ResultDesc': str(e)})
    
    return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid request method'})

# ===== Public Views =====

@login_required
def fee_summary(request):
    """Fee summary for all users"""
    if request.user.is_admin():
        student_fees = StudentFee.objects.all()
    elif request.user.is_teacher():
        try:
            teacher = request.user.teacher_profile
            classes = teacher.get_classes_list()
            student_fees = StudentFee.objects.filter(
                student__grade__in=classes
            )
        except:
            student_fees = StudentFee.objects.none()
    elif request.user.is_student():
        try:
            student = Student.objects.get(user=request.user)
            student_fees = StudentFee.objects.filter(student=student)
        except:
            student_fees = StudentFee.objects.none()
    else:
        student_fees = StudentFee.objects.none()
    
    return render(request, 'payments/fee_summary.html', {
        'student_fees': student_fees,
        'user': request.user,
    })


@login_required
def generate_receipt(request, payment_id):
    """Generate and display payment receipt"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Check if user has permission to view this receipt
    if not (request.user.is_admin() or 
            (request.user.is_student() and payment.student.user == request.user)):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    try:
        receipt = PaymentReceipt.objects.get(payment=payment)
    except PaymentReceipt.DoesNotExist:
        receipt = PaymentReceipt.objects.create(payment=payment)
    
    # Calculate balance information
    if payment.student_fee:
        previous_balance = payment.student_fee.balance + payment.amount
        new_balance = payment.student_fee.balance
    else:
        previous_balance = None
        new_balance = None
    
    return render(request, 'payments/payment_receipt.html', {
        'payment': payment,
        'receipt': receipt,
        'previous_balance': previous_balance,
        'new_balance': new_balance,
    })

@login_required
@user_passes_test(is_admin)
def financial_report(request):
    """Generate financial reports"""
    # Get date range from request or use default (current month)
    from_date = request.GET.get('from_date', timezone.now().replace(day=1).date())
    to_date = request.GET.get('to_date', timezone.now().date())
    
    # Convert string dates to date objects
    if isinstance(from_date, str):
        from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
    if isinstance(to_date, str):
        to_date = datetime.strptime(to_date, '%Y-%m-%d').date()
    
    # Get payments in date range
    payments = Payment.objects.filter(
        payment_date__date__range=[from_date, to_date],
        status='completed'
    )
    
    # Calculate statistics
    total_payments = payments.aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Group by payment method
    payment_methods = payments.values('payment_method').annotate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    # Get student fee statistics
    student_fees = StudentFee.objects.all()
    total_due = student_fees.aggregate(Sum('amount_due'))['amount_due__sum'] or 0
    total_paid_fees = student_fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
    total_balance = student_fees.aggregate(Sum('balance'))['balance__sum'] or 0
    
    return render(request, 'payments/financial_report.html', {
        'payments': payments,
        'total_payments': total_payments,
        'payment_methods': payment_methods,
        'student_fees': student_fees,
        'total_due': total_due,
        'total_paid_fees': total_paid_fees,
        'total_balance': total_balance,
        'from_date': from_date,
        'to_date': to_date,
    })

@login_required
def download_receipt(request, payment_id):
    """Download receipt as PDF"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Check permissions
    if not (request.user.is_admin() or 
            (request.user.is_student() and payment.student.user == request.user)):
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    # In a real implementation, you would generate a PDF here
    # For now, redirect to the HTML receipt
    return redirect('generate_receipt', payment_id=payment_id)