from django.core.management.base import BaseCommand
from apps.compliance.models import DataRetentionRule


class Command(BaseCommand):
    help = 'Setup default data retention rules for GDPR compliance'
    
    def handle(self, *args, **kwargs):
        self.stdout.write('Setting up default data retention rules...')
        
        rules = [
            {
                'rule_name': 'Inactive User Anonymization',
                'data_type': 'user_account',
                'retention_period_days': 730,  # 2 years
                'action_type': 'anonymize',
                'description': 'Anonymize user data after 2 years of inactivity',
                'legal_basis': 'GDPR Article 5(1)(e) - Storage limitation',
            },
            {
                'rule_name': 'Completed Order Archival',
                'data_type': 'order_data',
                'retention_period_days': 1825,  # 5 years
                'action_type': 'archive',
                'description': 'Archive completed order data after 5 years',
                'legal_basis': 'Tax and legal compliance requirements',
            },
            {
                'rule_name': 'Payment Record Retention',
                'data_type': 'payment_data',
                'retention_period_days': 2555,  # 7 years
                'action_type': 'archive',
                'description': 'Retain payment records for 7 years for tax purposes',
                'legal_basis': 'Financial regulations and tax laws',
            },
            {
                'rule_name': 'Audit Log Deletion',
                'data_type': 'logs',
                'retention_period_days': 365,  # 1 year
                'action_type': 'delete',
                'description': 'Delete system audit logs after 1 year',
                'legal_basis': 'GDPR Article 5(1)(e) - Storage limitation',
            },
            {
                'rule_name': 'Temporary File Cleanup',
                'data_type': 'backups',
                'retention_period_days': 30,
                'action_type': 'delete',
                'description': 'Delete temporary backup files after 30 days',
                'legal_basis': 'Data minimization principle',
            },
        ]
        
        for rule_data in rules:
            rule, created = DataRetentionRule.objects.update_or_create(
                rule_name=rule_data['rule_name'],
                defaults=rule_data
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created rule: {rule.rule_name}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Updated rule: {rule.rule_name}'))
        
        self.stdout.write(self.style.SUCCESS('Successfully setup data retention rules'))