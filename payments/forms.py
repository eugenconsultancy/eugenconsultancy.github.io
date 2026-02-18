from django import forms
from .models import FeeStructure, StudentFee, AdditionalCharge, Payment
from students.models import Student
import datetime

class FeeStructureForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = [
            'name', 'description', 'grade', 'term', 'academic_year',
            'tuition_fee', 'boarding_fee', 'activity_fee', 'exam_fee',
            'library_fee', 'medical_fee', 'sports_fee', 'development_fee',
            'other_charges', 'late_payment_fee', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'academic_year': forms.TextInput(attrs={'placeholder': 'e.g., 2024'}),
        }

class StudentFeeForm(forms.ModelForm):
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = StudentFee
        fields = ['student', 'fee_structure', 'additional_charges', 'penalty_charges', 'due_date']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'additional_charges': forms.NumberInput(attrs={'step': '0.01'}),
            'penalty_charges': forms.NumberInput(attrs={'step': '0.01'}),
        }

class AdditionalChargeForm(forms.ModelForm):
    class Meta:
        model = AdditionalCharge
        fields = ['student', 'charge_type', 'description', 'amount', 'due_date']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'step': '0.01'}),
        }

class MpesaPaymentForm(forms.Form):
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': '2547XXXXXXXX',
            'pattern': '^254[0-9]{9}$'
        })
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional payment description'})
    )
    
    def clean_phone_number(self):
        phone = self.cleaned_data['phone_number']
        if not phone.startswith('254'):
            raise forms.ValidationError("Phone number must start with 254")
        if len(phone) != 12:
            raise forms.ValidationError("Phone number must be 12 digits (254XXXXXXXXX)")
        return phone

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['student_fee', 'amount', 'payment_method', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'amount': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.is_student():
            try:
                student = Student.objects.get(user=user)
                self.fields['student_fee'].queryset = StudentFee.objects.filter(student=student)
            except Student.DoesNotExist:
                self.fields['student_fee'].queryset = StudentFee.objects.none()