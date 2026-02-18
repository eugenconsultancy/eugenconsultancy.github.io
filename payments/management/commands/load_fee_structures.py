from django.core.management.base import BaseCommand
from payments.models import FeeStructure
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Loads initial fee structure data'
    
    def handle(self, *args, **kwargs):
        fee_structures = [
            {
                'name': 'Form 1 Term 1 Fees 2024',
                'description': 'Form 1 First Term Fees for 2024 Academic Year',
                'grade': 'form1',
                'term': 'term1',
                'academic_year': '2024',
                'tuition_fee': 25000.00,
                'boarding_fee': 35000.00,
                'activity_fee': 5000.00,
                'exam_fee': 2000.00,
                'library_fee': 1000.00,
                'medical_fee': 3000.00,
                'sports_fee': 2000.00,
                'development_fee': 5000.00,
                'other_charges': 3000.00,
                'late_payment_fee': 1000.00,
                'is_active': True,
            },
            {
                'name': 'Form 2 Term 1 Fees 2024',
                'description': 'Form 2 First Term Fees for 2024 Academic Year',
                'grade': 'form2',
                'term': 'term1',
                'academic_year': '2024',
                'tuition_fee': 24000.00,
                'boarding_fee': 34000.00,
                'activity_fee': 4500.00,
                'exam_fee': 2000.00,
                'library_fee': 1000.00,
                'medical_fee': 3000.00,
                'sports_fee': 2000.00,
                'development_fee': 5000.00,
                'other_charges': 3000.00,
                'late_payment_fee': 1000.00,
                'is_active': True,
            },
            {
                'name': 'Form 3 Term 1 Fees 2024',
                'description': 'Form 3 First Term Fees for 2024 Academic Year',
                'grade': 'form3',
                'term': 'term1',
                'academic_year': '2024',
                'tuition_fee': 26000.00,
                'boarding_fee': 36000.00,
                'activity_fee': 5500.00,
                'exam_fee': 2500.00,
                'library_fee': 1500.00,
                'medical_fee': 3500.00,
                'sports_fee': 2500.00,
                'development_fee': 6000.00,
                'other_charges': 3500.00,
                'late_payment_fee': 1500.00,
                'is_active': True,
            },
            {
                'name': 'Form 4 Term 1 Fees 2024',
                'description': 'Form 4 First Term Fees for 2024 Academic Year',
                'grade': 'form4',
                'term': 'term1',
                'academic_year': '2024',
                'tuition_fee': 28000.00,
                'boarding_fee': 38000.00,
                'activity_fee': 6000.00,
                'exam_fee': 3000.00,
                'library_fee': 2000.00,
                'medical_fee': 4000.00,
                'sports_fee': 3000.00,
                'development_fee': 7000.00,
                'other_charges': 4000.00,
                'late_payment_fee': 2000.00,
                'is_active': True,
            },
        ]
        
        for fee_data in fee_structures:
            fee, created = FeeStructure.objects.get_or_create(
                grade=fee_data['grade'],
                term=fee_data['term'],
                academic_year=fee_data['academic_year'],
                defaults=fee_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created fee structure: {fee.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Fee structure already exists: {fee.name}'))
        
        self.stdout.write(self.style.SUCCESS('Successfully loaded fee structures'))