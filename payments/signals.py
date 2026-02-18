from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Payment, StudentFee, AdditionalCharge
from django.db.models import Sum

@receiver(post_save, sender=Payment)
def update_student_fee_on_payment(sender, instance, created, **kwargs):
    """
    Update student fee balance when a payment is saved
    """
    if instance.status == 'completed' and instance.student_fee:
        # Get the student fee
        student_fee = instance.student_fee
        
        # Recalculate total paid amount for this fee
        total_paid = Payment.objects.filter(
            student_fee=student_fee,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Update the student fee
        student_fee.amount_paid = total_paid
        student_fee.save()
        
        # If the fee is now fully paid, update paid_date
        if student_fee.is_paid and not student_fee.paid_date:
            student_fee.paid_date = timezone.now().date()
            student_fee.save()

@receiver(post_save, sender=AdditionalCharge)
def update_student_fee_on_charge(sender, instance, created, **kwargs):
    """
    Update student fee when an additional charge is added
    """
    if created and not instance.is_paid:
        # Find the most recent active fee structure for the student
        student_fee = StudentFee.objects.filter(
            student=instance.student,
            fee_structure__is_active=True
        ).first()
        
        if student_fee:
            # Add the charge amount to the student fee
            student_fee.additional_charges += instance.amount
            student_fee.save()

@receiver(pre_save, sender=StudentFee)
def calculate_fee_totals(sender, instance, **kwargs):
    """
    Calculate fee totals before saving
    """
    if not instance.pk:  # New instance
        # Calculate initial amount due
        if instance.fee_structure:
            instance.amount_due = instance.fee_structure.total_fee + instance.additional_charges + instance.penalty_charges
            instance.balance = instance.amount_due - instance.amount_paid
            instance.is_paid = instance.balance <= 0

@receiver(post_save, sender=Payment)
def create_receipt_on_payment_completion(sender, instance, created, **kwargs):
    """
    Create a receipt when payment is completed
    """
    if instance.status == 'completed':
        # Check if receipt already exists
        from .models import PaymentReceipt
        receipt, created = PaymentReceipt.objects.get_or_create(
            payment=instance,
            defaults={'receipt_number': ''}
        )
        
        if created:
            # Generate receipt number if not already set
            if not receipt.receipt_number:
                receipt.save()  # This will trigger the receipt number generation

@receiver(post_save, sender=StudentFee)
def apply_late_payment_penalty(sender, instance, **kwargs):
    """
    Apply late payment penalty if due date has passed
    """
    if not instance.is_paid and instance.due_date < timezone.now().date():
        # Check if penalty already applied
        penalty_applied = AdditionalCharge.objects.filter(
            student=instance.student,
            charge_type='other',
            description__contains='Late payment penalty'
        ).exists()
        
        if not penalty_applied and instance.fee_structure.late_payment_fee > 0:
            # Apply late payment penalty
            AdditionalCharge.objects.create(
                student=instance.student,
                charge_type='other',
                description=f'Late payment penalty for {instance.fee_structure.term} {instance.fee_structure.academic_year}',
                amount=instance.fee_structure.late_payment_fee,
                due_date=instance.due_date,
                added_by=None  # System-generated
            )