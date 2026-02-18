from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import FeeStructure, StudentFee, Payment, AdditionalCharge, PaymentReceipt

@admin.register(FeeStructure)
class FeeStructureAdmin(ModelAdmin):
    list_display = ('name', 'grade', 'term', 'academic_year', 'total_fee', 'is_active')
    list_filter = ('grade', 'term', 'academic_year', 'is_active')
    search_fields = ('name', 'description', 'academic_year')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'grade', 'term', 'academic_year', 'is_active')
        }),
        ('Fee Breakdown', {
            'fields': (
                'tuition_fee', 'boarding_fee', 'activity_fee', 'exam_fee',
                'library_fee', 'medical_fee', 'sports_fee', 'development_fee'
            )
        }),
        ('Additional Charges', {
            'fields': ('other_charges', 'late_payment_fee')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def total_fee(self, obj):
        return f"Ksh {obj.total_fee:,.2f}"
    total_fee.short_description = 'Total Fee'

@admin.register(StudentFee)
class StudentFeeAdmin(ModelAdmin):
    list_display = ('student', 'fee_structure', 'amount_due', 'amount_paid', 'balance', 'is_paid', 'due_date')
    list_filter = ('fee_structure__grade', 'fee_structure__term', 'is_paid', 'due_date')
    search_fields = ('student__user__username', 'student__admission_number', 'student__user__first_name', 'student__user__last_name')
    readonly_fields = ('amount_due', 'balance', 'is_paid', 'created_at', 'updated_at')
    fieldsets = (
        ('Student Information', {
            'fields': ('student', 'fee_structure')
        }),
        ('Payment Information', {
            'fields': ('amount_paid', 'additional_charges', 'penalty_charges', 'due_date', 'paid_date')
        }),
        ('Calculated Fields', {
            'fields': ('amount_due', 'balance', 'is_paid'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_due_formatted(self, obj):
        return f"Ksh {obj.amount_due:,.2f}"
    amount_due_formatted.short_description = 'Amount Due'
    
    def amount_paid_formatted(self, obj):
        return f"Ksh {obj.amount_paid:,.2f}"
    amount_paid_formatted.short_description = 'Amount Paid'
    
    def balance_formatted(self, obj):
        return f"Ksh {obj.balance:,.2f}"
    balance_formatted.short_description = 'Balance'

@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ('student', 'amount', 'payment_method', 'status', 'payment_date', 'confirmed_by')
    list_filter = ('payment_method', 'status', 'payment_date', 'confirmed_by')
    search_fields = ('student__user__username', 'student__admission_number', 'transaction_id', 'mpesa_code', 'receipt_number')
    readonly_fields = ('payment_date', 'created_at', 'updated_at')
    fieldsets = (
        ('Payment Information', {
            'fields': ('student_fee', 'student', 'amount', 'payment_method', 'status')
        }),
        ('Transaction Details', {
            'fields': ('transaction_id', 'receipt_number', 'mpesa_code', 'phone_number', 'description')
        }),
        ('Confirmation', {
            'fields': ('confirmed_by', 'confirmed_at')
        }),
        ('Timestamps', {
            'fields': ('payment_date', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_formatted(self, obj):
        return f"Ksh {obj.amount:,.2f}"
    amount_formatted.short_description = 'Amount'

@admin.register(AdditionalCharge)
class AdditionalChargeAdmin(ModelAdmin):
    list_display = ('student', 'charge_type', 'amount', 'is_paid', 'due_date', 'added_by')
    list_filter = ('charge_type', 'is_paid', 'due_date', 'added_by')
    search_fields = ('student__user__username', 'student__admission_number', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Charge Information', {
            'fields': ('student', 'charge_type', 'description', 'amount')
        }),
        ('Payment Status', {
            'fields': ('is_paid', 'due_date', 'paid_date')
        }),
        ('Administration', {
            'fields': ('added_by',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def amount_formatted(self, obj):
        return f"Ksh {obj.amount:,.2f}"
    amount_formatted.short_description = 'Amount'

@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(ModelAdmin):
    list_display = ('receipt_number', 'payment', 'generated_at')
    list_filter = ('generated_at',)
    search_fields = ('receipt_number', 'payment__transaction_id')
    readonly_fields = ('receipt_number', 'generated_at')
    fieldsets = (
        ('Receipt Information', {
            'fields': ('payment', 'receipt_number', 'pdf_file')
        }),
        ('Timestamps', {
            'fields': ('generated_at',),
            'classes': ('collapse',)
        }),
    )