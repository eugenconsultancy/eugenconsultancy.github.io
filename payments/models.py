from django.db import models
from students.models import Student
from django.core.validators import MinValueValidator
from decimal import Decimal

class FeeStructure(models.Model):
    TERM_CHOICES = (
        ('term1', 'Term 1'),
        ('term2', 'Term 2'),
        ('term3', 'Term 3'),
        ('term4', 'Term 4'),
    )
    
    GRADE_CHOICES = (
        ('form1', 'Form 1'),
        ('form2', 'Form 2'),
        ('form3', 'Form 3'),
        ('form4', 'Form 4'),
        ('form5', 'Form 5'),
        ('form6', 'Form 6'),
    )
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    grade = models.CharField(max_length=20, choices=GRADE_CHOICES)
    term = models.CharField(max_length=20, choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=20)
    
    # Fee breakdown
    tuition_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    boarding_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activity_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    exam_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    library_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medical_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sports_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    development_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Additional charges
    other_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    late_payment_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['grade', 'term', 'academic_year']
        ordering = ['academic_year', 'term', 'grade']
    
    def __str__(self):
        return f"{self.name} - {self.grade} {self.term} {self.academic_year}"
    
    @property
    def total_fee(self):
        total = sum([
            self.tuition_fee,
            self.boarding_fee,
            self.activity_fee,
            self.exam_fee,
            self.library_fee,
            self.medical_fee,
            self.sports_fee,
            self.development_fee,
            self.other_charges,
        ])
        return total

class StudentFee(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fees')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE, related_name='student_fees')
    
    # Payment status
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Additional charges specific to student
    additional_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    penalty_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Payment status
    is_paid = models.BooleanField(default=False)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-due_date', 'student']
        unique_together = ['student', 'fee_structure']
    
    def __str__(self):
        return f"{self.student} - {self.fee_structure} - Balance: {self.balance}"
    
    def save(self, *args, **kwargs):
        # Calculate total amount due
        total_fee = self.fee_structure.total_fee
        self.amount_due = total_fee + self.additional_charges + self.penalty_charges
        
        # Calculate balance
        self.balance = self.amount_due - self.amount_paid
        
        # Update payment status
        self.is_paid = self.balance <= 0
        
        super().save(*args, **kwargs)
    
    @property
    def total_charges(self):
        return self.additional_charges + self.penalty_charges

class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('mpesa', 'M-Pesa'),
        ('bank', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('other', 'Other'),
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    
    student_fee = models.ForeignKey(StudentFee, on_delete=models.CASCADE, related_name='payments')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='mpesa')
    payment_date = models.DateTimeField(auto_now_add=True)
    transaction_id = models.CharField(max_length=100, unique=True, blank=True)
    receipt_number = models.CharField(max_length=100, blank=True)
    
    # M-Pesa specific fields
    mpesa_code = models.CharField(max_length=50, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    description = models.TextField(blank=True)
    
    confirmed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.student} - {self.amount} - {self.payment_method} - {self.status}"

class AdditionalCharge(models.Model):
    CHARGE_TYPE_CHOICES = (
        ('library', 'Library Fine'),
        ('damage', 'Damage Fee'),
        ('uniform', 'Uniform Fee'),
        ('book', 'Book Replacement'),
        ('sports', 'Sports Equipment'),
        ('trip', 'School Trip'),
        ('other', 'Other'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='additional_charges')
    charge_type = models.CharField(max_length=20, choices=CHARGE_TYPE_CHOICES)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    
    # Status
    is_paid = models.BooleanField(default=False)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    
    added_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-due_date', 'student']
    
    def __str__(self):
        return f"{self.student} - {self.charge_type} - {self.amount}"

class PaymentReceipt(models.Model):
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='receipt')
    receipt_number = models.CharField(max_length=50, unique=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    pdf_file = models.FileField(upload_to='receipts/', null=True, blank=True)
    
    def __str__(self):
        return f"Receipt {self.receipt_number} - {self.payment}"
    
    def generate_receipt_number(self):
        from datetime import datetime
        date_str = datetime.now().strftime('%Y%m%d')
        return f"RCPT-{date_str}-{self.id:06d}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        super().save(*args, **kwargs)