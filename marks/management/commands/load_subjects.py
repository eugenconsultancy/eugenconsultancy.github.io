from django.core.management.base import BaseCommand
from marks.models import Subject

class Command(BaseCommand):
    help = 'Loads initial subject data'
    
    def handle(self, *args, **kwargs):
        subjects = [
            # Humanities
            {'name': 'History', 'code': 'HIST101', 'category': 'humanities'},
            {'name': 'Geography', 'code': 'GEOG101', 'category': 'humanities'},
            {'name': 'Religious Education', 'code': 'RE101', 'category': 'humanities'},
            {'name': 'Life Skills', 'code': 'LIFE101', 'category': 'humanities'},
            {'name': 'Business Studies', 'code': 'BUS101', 'category': 'humanities'},
            
            # Creative Arts
            {'name': 'Music', 'code': 'MUS101', 'category': 'creative_arts'},
            {'name': 'Art and Design', 'code': 'ART101', 'category': 'creative_arts'},
            {'name': 'Creative Arts', 'code': 'CREA101', 'category': 'creative_arts'},
            
            # Technical Subjects
            {'name': 'Computer Studies', 'code': 'COMP101', 'category': 'technical'},
            {'name': 'Technical Drawing', 'code': 'TECH101', 'category': 'technical'},
            {'name': 'Agriculture', 'code': 'AGRI101', 'category': 'technical'},
            
            # Sciences
            {'name': 'Mathematics', 'code': 'MATH101', 'category': 'sciences'},
            {'name': 'Physics', 'code': 'PHYS101', 'category': 'sciences'},
            {'name': 'Chemistry', 'code': 'CHEM101', 'category': 'sciences'},
            {'name': 'Biology', 'code': 'BIO101', 'category': 'sciences'},
            
            # Languages
            {'name': 'English', 'code': 'ENG101', 'category': 'languages'},
            {'name': 'Kiswahili', 'code': 'KIS101', 'category': 'languages'},
            {'name': 'French', 'code': 'FREN101', 'category': 'languages'},
        ]
        
        for subject_data in subjects:
            subject, created = Subject.objects.get_or_create(
                code=subject_data['code'],
                defaults=subject_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created subject: {subject.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Subject already exists: {subject.name}'))
        
        self.stdout.write(self.style.SUCCESS('Successfully loaded all subjects'))