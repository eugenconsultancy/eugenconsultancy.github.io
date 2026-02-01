# apps/compliance/services.py
import json
import hashlib
import csv
import zipfile
import io
import os
from typing import Dict, List, Optional, TYPE_CHECKING
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.conf import settings
import uuid

# Use TYPE_CHECKING for type hints to avoid circular imports
if TYPE_CHECKING:
    from .models import ConsentLog, DataRetentionRule, DataRequest, AuditLog
    from apps.accounts.models import User
    from apps.orders.models import Order
    from apps.payments.models import Payment


class ConsentService:
    """Service for managing user consent records."""
    
    def __init__(self):
        pass
    
    def _get_consent_log_model(self):
        """Helper method to get ConsentLog model."""
        from .models import ConsentLog
        return ConsentLog
    
    def _get_audit_log_model(self):
        """Helper method to get AuditLog model."""
        from .models import AuditLog
        return AuditLog
    
    def give_consent(self, user: "User", consent_type: str, ip_address: Optional[str] = None, 
                    user_agent: Optional[str] = None, consent_text: str = "", version: str = ""):
        """
        Record that a user has given consent.
        """
        ConsentLog = self._get_consent_log_model()
        AuditLog = self._get_audit_log_model()
        
        if not consent_type:
            raise ValidationError("Consent type is required")
        
        consent_log = ConsentLog.objects.create(
            user=user,
            consent_type=consent_type,
            consent_given=True,
            ip_address=ip_address,
            user_agent=user_agent or "",
            consent_text=consent_text,
            version=version,
        )
        
        # Log the consent action
        AuditLog.objects.create(
            user=user,
            action_type='create',
            model_name='ConsentLog',
            object_id=str(consent_log.id),
            changes={'consent_type': consent_type, 'consent_given': True},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        return consent_log
    
    def withdraw_consent(self, user: "User", consent_type: str, ip_address: Optional[str] = None, 
                        user_agent: Optional[str] = None, reason: str = ""):
        """
        Record that a user has withdrawn consent.
        """
        ConsentLog = self._get_consent_log_model()
        AuditLog = self._get_audit_log_model()
        
        if not consent_type:
            raise ValidationError("Consent type is required")
        
        # Check if this consent can be withdrawn (some are required)
        if not self._is_withdrawable(consent_type):
            raise ValidationError(
                f"Consent type '{consent_type}' cannot be withdrawn as it's required for service operation"
            )
        
        # Check if user has actually given this consent
        has_given_consent = ConsentLog.objects.filter(
            user=user,
            consent_type=consent_type,
            consent_given=True
        ).exists()
        
        if not has_given_consent:
            raise ValidationError(
                f"User has not given consent for '{consent_type}', nothing to withdraw"
            )
        
        consent_log = ConsentLog.objects.create(
            user=user,
            consent_type=consent_type,
            consent_given=False,
            ip_address=ip_address,
            user_agent=user_agent or "",
            consent_text=f"Consent withdrawn. Reason: {reason}" if reason else "Consent withdrawn",
            version="N/A",
        )
        
        # Log the withdrawal action
        AuditLog.objects.create(
            user=user,
            action_type='update',
            model_name='ConsentLog',
            object_id=str(consent_log.id),
            changes={'consent_type': consent_type, 'consent_given': False},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        return consent_log
    
    def _is_withdrawable(self, consent_type: str) -> bool:
        """
        Check if a consent type can be withdrawn.
        """
        # Required consents that cannot be withdrawn
        non_withdrawable = ['registration', 'terms', 'privacy', 'data_processing']
        return consent_type not in non_withdrawable
    
    def get_user_consents(self, user: "User") -> Dict:
        """
        Get all consents for a user with their current status.
        """
        ConsentLog = self._get_consent_log_model()
        
        consents = {}
        
        # Get consent type choices
        consent_choices = getattr(ConsentLog.ConsentType, 'choices', [])
        if not consent_choices:
            # Fallback if choices not defined
            consent_choices = [
                ('registration', 'Registration'),
                ('terms', 'Terms of Service'),
                ('privacy', 'Privacy Policy'),
                ('marketing', 'Marketing Emails'),
                ('cookies', 'Cookies'),
                ('data_processing', 'Data Processing'),
            ]
        
        # Get latest consent record for each type
        for consent_type, _ in consent_choices:
            latest_consent = ConsentLog.objects.filter(
                user=user,
                consent_type=consent_type
            ).order_by('-created_at').first()
            
            if latest_consent:
                consents[consent_type] = {
                    'given': latest_consent.consent_given,
                    'date': latest_consent.created_at,
                    'version': latest_consent.version,
                    'ip_address': latest_consent.ip_address,
                }
            else:
                # No consent record exists for this type
                consents[consent_type] = {
                    'given': False,
                    'date': None,
                    'version': None,
                    'ip_address': None,
                }
        
        return consents
    
    def get_consent_history(self, user: "User", consent_type: Optional[str] = None, limit: int = 50):
        """
        Get consent history for a user.
        """
        ConsentLog = self._get_consent_log_model()
        
        queryset = ConsentLog.objects.filter(user=user)
        
        if consent_type:
            queryset = queryset.filter(consent_type=consent_type)
        
        return queryset.order_by('-created_at')[:limit]
    
    def has_consent(self, user: "User", consent_type: str) -> bool:
        """
        Check if a user currently has a specific consent.
        """
        ConsentLog = self._get_consent_log_model()
        
        latest_consent = ConsentLog.objects.filter(
            user=user,
            consent_type=consent_type
        ).order_by('-created_at').first()
        
        return latest_consent.consent_given if latest_consent else False


class AuditService:
    """Service for managing audit logs."""
    
    @staticmethod
    def _get_audit_log_model():
        """Helper to get AuditLog model."""
        from .models import AuditLog
        return AuditLog
    
    @staticmethod
    def log_action(user: Optional["User"], action_type: str, model_name: str, object_id: Optional[str] = None, 
                   changes: Optional[Dict] = None, before_state: Optional[Dict] = None, after_state: Optional[Dict] = None,
                   ip_address: Optional[str] = None, user_agent: Optional[str] = None, request_path: Optional[str] = None,
                   session_key: Optional[str] = None):
        """
        Log an action to the audit log.
        """
        AuditLog = AuditService._get_audit_log_model()
        
        audit_log = AuditLog.objects.create(
            user=user,
            action_type=action_type,
            model_name=model_name,
            object_id=object_id or "",
            changes=changes,
            before_state=before_state,
            after_state=after_state,
            ip_address=ip_address,
            user_agent=user_agent or "",
            request_path=request_path or "",
            session_key=session_key or "",
        )
        
        return audit_log
    
    @staticmethod
    def log_data_request_submission(user: "User", request_type: str, request_id: uuid.UUID):
        """Log data request submission."""
        return AuditService.log_action(
            user=user,
            action_type='create',
            model_name='DataRequest',
            object_id=str(request_id),
            changes={'request_type': request_type, 'status': 'received'},
        )
    
    @staticmethod
    def log_consent_change(user: "User", consent_type: str, given: bool = True):
        """Log consent change."""
        return AuditService.log_action(
            user=user,
            action_type='update' if given else 'delete',
            model_name='ConsentLog',
            changes={'consent_type': consent_type, 'consent_given': given},
        )


class DataRequestService:
    """Service for handling GDPR data subject requests."""
    
    def __init__(self):
        self.User = get_user_model()
    
    def _get_data_request_model(self):
        """Helper method to get DataRequest model."""
        from .models import DataRequest
        return DataRequest
    
    def _get_consent_log_model(self):
        """Helper method to get ConsentLog model."""
        from .models import ConsentLog
        return ConsentLog
    
    def _get_audit_log_model(self):
        """Helper method to get AuditLog model."""
        from .models import AuditLog
        return AuditLog
    
    @transaction.atomic
    def create_data_request(self, user_id: int, request_type: str, description: str):
        """
        Create a new data request.
        """
        DataRequest = self._get_data_request_model()
        user = self.User.objects.get(id=user_id)
        
        # Check for duplicate pending requests
        existing_request = DataRequest.objects.filter(
            user=user,
            request_type=request_type,
            status__in=['received', 'verifying', 'processing']
        ).first()
        
        if existing_request:
            raise ValidationError(
                f"You already have a pending {request_type} request (ID: {existing_request.request_id})"
            )
        
        # Create request
        request = DataRequest.objects.create(
            user=user,
            request_type=request_type,
            description=description,
            status='received',
        )
        
        return request
    
    @transaction.atomic
    def verify_request(self, request_id: uuid.UUID, admin_user: "User", verification_method: str):
        """
        Verify a data request.
        """
        if not admin_user.is_staff:
            raise ValidationError("Only staff can verify data requests")
        
        DataRequest = self._get_data_request_model()
        request = DataRequest.objects.get(request_id=request_id)
        
        if request.status != 'received':
            raise ValidationError(f"Cannot verify request in status: {request.status}")
        
        request.status = 'verifying'
        request.verification_method = verification_method
        request.verified_by = admin_user
        request.verification_date = timezone.now()
        request.save()
        
        return request
    
    @transaction.atomic
    def process_access_request(self, request_id: uuid.UUID) -> Dict:
        """
        Process a data access request.
        """
        DataRequest = self._get_data_request_model()
        request = DataRequest.objects.get(request_id=request_id)
        
        if request.request_type != 'access':
            raise ValidationError(f"Cannot process {request.request_type} as access request")
        
        if request.status != 'verifying':
            raise ValidationError(f"Cannot process request in status: {request.status}")
        
        # Export user data (simplified for now)
        export_data = self._export_user_data(request.user)
        
        # Update request
        request.status = 'processing'
        request.data_provided = json.dumps(export_data['summary'], indent=2)
        request.save()
        
        # Generate export file
        file_path = self._generate_export_file(request.user, export_data)
        request.file_path = file_path
        
        # Complete request
        request.status = 'completed'
        request.completed_at = timezone.now()
        request.save()
        
        return export_data
    
    def _export_user_data(self, user: "User") -> Dict:
        """Export all user data for GDPR access request."""
        ConsentLog = self._get_consent_log_model()
        AuditLog = self._get_audit_log_model()
        
        # Import other models inside method to avoid circular imports
        try:
            from apps.orders.models import Order
        except ImportError:
            Order = None
        
        try:
            from apps.payments.models import Payment
        except ImportError:
            Payment = None
        
        data = {
            'user': self._export_user_profile(user),
            'consents': self._export_consents(user),
            'orders': self._export_orders(user) if Order else [],
            'payments': self._export_payments(user) if Payment else [],
            'audit_logs': self._export_audit_logs(user),
            'summary': {},
        }
        
        # Create summary
        data['summary'] = {
            'export_date': timezone.now().isoformat(),
            'user_id': user.id,
            'email': user.email,
            'total_orders': len(data['orders']),
            'total_payments': len(data['payments']),
            'total_consents': len(data['consents']),
            'data_categories': list(data.keys()),
        }
        
        return data
    
    def _export_user_profile(self, user: "User") -> Dict:
        """Export user profile data."""
        profile_data = {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
        }
        
        return profile_data
    
    def _export_consents(self, user: "User") -> List[Dict]:
        """Export user consent history."""
        ConsentLog = self._get_consent_log_model()
        
        consents = ConsentLog.objects.filter(user=user)
        return [
            {
                'consent_type': consent.consent_type,
                'consent_given': consent.consent_given,
                'created_at': consent.created_at.isoformat(),
                'ip_address': consent.ip_address,
            }
            for consent in consents
        ]
    
    def _export_orders(self, user: "User") -> List[Dict]:
        """Export user orders."""
        try:
            from apps.orders.models import Order
            orders = Order.objects.filter(Q(client=user) | Q(writer=user))
            
            order_list = []
            for order in orders:
                order_data = {
                    'order_number': order.order_number,
                    'title': order.title,
                    'state': order.state,
                    'price': str(order.price) if hasattr(order, 'price') else '0',
                    'created_at': order.created_at.isoformat() if hasattr(order, 'created_at') else None,
                }
                order_list.append(order_data)
            
            return order_list
        except ImportError:
            return []
    
    def _export_payments(self, user: "User") -> List[Dict]:
        """Export user payments."""
        try:
            from apps.payments.models import Payment
            payments = Payment.objects.filter(user=user)
            
            payment_list = []
            for payment in payments:
                payment_data = {
                    'reference_number': payment.reference_number,
                    'amount': str(payment.amount),
                    'state': payment.state,
                    'created_at': payment.created_at.isoformat(),
                }
                payment_list.append(payment_data)
            
            return payment_list
        except ImportError:
            return []
    
    def _export_audit_logs(self, user: "User") -> List[Dict]:
        """Export user audit logs."""
        AuditLog = self._get_audit_log_model()
        
        logs = AuditLog.objects.filter(user=user)
        
        log_list = []
        for log in logs:
            log_data = {
                'action_type': log.action_type,
                'model_name': log.model_name,
                'object_id': log.object_id,
                'timestamp': log.timestamp.isoformat(),
                'ip_address': log.ip_address,
            }
            log_list.append(log_data)
        
        return log_list
    
    def _generate_export_file(self, user: "User", export_data: Dict) -> str:
        """Generate export file for user data."""
        # Create directory if it doesn't exist
        export_dir = os.path.join(settings.MEDIA_ROOT, 'data_exports', str(user.id))
        os.makedirs(export_dir, exist_ok=True)
        
        # Generate filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'gdpr_export_{user.id}_{timestamp}.zip'
        filepath = os.path.join(export_dir, filename)
        
        # Create ZIP file
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add summary as JSON
            summary_json = json.dumps(export_data['summary'], indent=2)
            zipf.writestr('summary.json', summary_json)
            
            # Add each data category as JSON
            for category, data in export_data.items():
                if category != 'summary':
                    data_json = json.dumps(data, indent=2, default=str)
                    zipf.writestr(f'{category}.json', data_json)
        
        # Return relative path for storage
        return f'data_exports/{user.id}/{filename}'


class DataRetentionService:
    """Service for managing data retention and deletion."""
    
    def __init__(self):
        self.User = get_user_model()
    
    def _get_data_retention_rule_model(self):
        """Helper method to get DataRetentionRule model."""
        from .models import DataRetentionRule
        return DataRetentionRule
    
    def _get_audit_log_model(self):
        """Helper method to get AuditLog model."""
        from .models import AuditLog
        return AuditLog
    
    def execute_rule(self, rule, dry_run: bool = False) -> Dict:
        """
        Execute a data retention rule.
        """
        DataRetentionRule = self._get_data_retention_rule_model()
        
        results = {
            'rule_id': str(rule.id),
            'rule_name': rule.rule_name,
            'action_type': rule.action_type,
            'dry_run': dry_run,
            'processed_count': 0,
            'errors': [],
            'details': {},
        }
        
        try:
            # Determine cutoff date
            cutoff_date = timezone.now() - timedelta(days=rule.retention_period_days)
            
            # Execute based on data type
            if rule.data_type == DataRetentionRule.DataType.USER_ACCOUNT:
                results.update(
                    self._process_user_accounts(rule, cutoff_date, dry_run)
                )
            elif rule.data_type == DataRetentionRule.DataType.ORDER_DATA:
                results.update(
                    self._process_order_data(rule, cutoff_date, dry_run)
                )
            elif rule.data_type == DataRetentionRule.DataType.LOGS:
                results.update(
                    self._process_logs(rule, cutoff_date, dry_run)
                )
            else:
                results['errors'].append(f'Unsupported data type: {rule.data_type}')
        
        except Exception as e:
            results['errors'].append(f'Execution failed: {str(e)}')
        
        return results
    
    def _process_user_accounts(self, rule, cutoff_date, dry_run):
        """Process user accounts for retention rule."""
        results = {}
        
        # Find inactive users older than cutoff
        users = self.User.objects.filter(
            Q(last_login__lt=cutoff_date) | Q(last_login__isnull=True),
            date_joined__lt=cutoff_date,
            is_active=True,
        )
        
        results['eligible_count'] = users.count()
        results['processed_count'] = 0
        
        if dry_run:
            return results
        
        for user in users:
            try:
                with transaction.atomic():
                    if rule.action_type == 'anonymize':
                        self._anonymize_user(user)
                    elif rule.action_type == 'delete':
                        self._delete_user(user)
                    
                    results['processed_count'] += 1
                    
            except Exception as e:
                results.setdefault('user_errors', []).append(f'User {user.id}: {str(e)}')
        
        return results
    
    def _process_order_data(self, rule, cutoff_date, dry_run):
        """Process order data for retention rule."""
        results = {}
        
        try:
            from apps.orders.models import Order
            # Find completed orders older than cutoff
            orders = Order.objects.filter(
                completed_at__lt=cutoff_date,
                state='completed',
            )
            
            results['eligible_count'] = orders.count()
            results['processed_count'] = 0
            
            if dry_run:
                return results
            
            for order in orders:
                try:
                    with transaction.atomic():
                        if rule.action_type == 'anonymize':
                            self._anonymize_order(order)
                        elif rule.action_type == 'archive':
                            self._archive_order(order)
                        
                        results['processed_count'] += 1
                        
                except Exception as e:
                    results.setdefault('order_errors', []).append(f'Order {order.id}: {str(e)}')
            
            return results
        except ImportError:
            results['errors'] = ['Orders app not available']
            return results
    
    def _process_logs(self, rule, cutoff_date, dry_run):
        """Process system logs for retention rule."""
        results = {}
        
        AuditLog = self._get_audit_log_model()
        
        # Find old audit logs
        logs = AuditLog.objects.filter(
            timestamp__lt=cutoff_date,
        )
        
        results['eligible_count'] = logs.count()
        
        if dry_run:
            return results
        
        if rule.action_type == 'delete':
            deleted_count, _ = logs.delete()
            results['processed_count'] = deleted_count
        
        return results
    
    def _anonymize_user(self, user: "User"):
        """Anonymize user data while preserving referential integrity."""
        # Generate anonymous identifier
        anonymous_id = hashlib.sha256(f"user_{user.id}_{timezone.now().timestamp()}".encode()).hexdigest()[:8]
        
        # Anonymize personal data
        user.email = f"anonymous_{anonymous_id}@anonymized.ebwriting"
        user.first_name = "Anonymized"
        user.last_name = "User"
        if hasattr(user, 'phone_number'):
            user.phone_number = ""
        
        # Add anonymization flag if exists
        if hasattr(user, 'data_anonymized'):
            user.data_anonymized = True
        
        # Clear sensitive fields
        user.set_unusable_password()
        
        user.save()
    
    def _delete_user(self, user: "User"):
        """Delete user and associated data."""
        # Check if deletion is allowed
        try:
            from apps.orders.models import Order
            from apps.payments.models import Payment
            
            pending_orders = Order.objects.filter(
                Q(client=user) | Q(writer=user),
                state__in=['draft', 'paid', 'assigned', 'in_progress', 'delivered']
            ).exists()
            
            pending_payments = Payment.objects.filter(
                user=user,
                state__in=['processing', 'held_in_escrow']
            ).exists()
            
            if pending_orders or pending_payments:
                raise ValidationError("Cannot delete user with pending orders or payments")
        
        except ImportError:
            pass  # If apps not available, skip validation
        
        # Anonymize first (safer than deletion)
        self._anonymize_user(user)
        
        # Mark for deletion (soft delete)
        user.is_active = False
        user.save()
    
    def _anonymize_order(self, order):
        """Anonymize order data while preserving financial records."""
        # Simple anonymization
        order.title = "Anonymized Order"
        order.description = "Anonymized content"
        order.save()
    
    def _archive_order(self, order):
        """Archive order data."""
        # Simple archiving marker
        if hasattr(order, 'admin_notes'):
            order.admin_notes = f"Archived on {timezone.now().date().isoformat()}\n{order.admin_notes}"
            order.save()