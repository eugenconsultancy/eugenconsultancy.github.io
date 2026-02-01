from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import User, WriterProfile, WriterVerificationStatus, WriterDocument
from apps.compliance.models import AuditLog, ConsentLog
from apps.notifications.tasks import send_user_notification


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create related profiles when a new user is created."""
    if created:
        # Create writer profile if user is a writer
        if instance.user_type == User.UserType.WRITER:
            WriterProfile.objects.create(user=instance)
            WriterVerificationStatus.objects.create(user=instance)
        
        # Log the creation
        AuditLog.objects.create(
            user=instance,
            action_type='create',
            model_name='User',
            object_id=str(instance.id),
            changes={'email': instance.email, 'user_type': instance.user_type},
        )
        
        # Send welcome notification
        send_user_notification.delay(
            user_id=instance.id,
            notification_type='welcome',
            subject=f'Welcome to EBWriting, {instance.get_short_name()}!',
        )


@receiver(pre_save, sender=User)
def log_user_changes(sender, instance, **kwargs):
    """Log changes to user model for audit trail."""
    if instance.pk:
        try:
            old_instance = User.objects.get(pk=instance.pk)
            
            changes = {}
            for field in ['email', 'user_type', 'is_active', 'is_staff']:
                old_value = getattr(old_instance, field)
                new_value = getattr(instance, field)
                if old_value != new_value:
                    changes[field] = {'old': old_value, 'new': new_value}
            
            if changes:
                AuditLog.objects.create(
                    user=instance,
                    action_type='update',
                    model_name='User',
                    object_id=str(instance.id),
                    changes=changes,
                    before_state={
                        'email': old_instance.email,
                        'user_type': old_instance.user_type,
                        'is_active': old_instance.is_active,
                        'is_staff': old_instance.is_staff,
                    },
                    after_state={
                        'email': instance.email,
                        'user_type': instance.user_type,
                        'is_active': instance.is_active,
                        'is_staff': instance.is_staff,
                    },
                )
        except User.DoesNotExist:
            pass


@receiver(post_save, sender=WriterDocument)
def handle_document_upload(sender, instance, created, **kwargs):
    """Handle document upload events."""
    if created:
        # Log document upload
        AuditLog.objects.create(
            user=instance.user,
            action_type='create',
            model_name='WriterDocument',
            object_id=str(instance.id),
            changes={
                'document_type': instance.document_type,
                'status': instance.status,
            },
        )
        
        # Notify admins of new document (if it's for verification)
        if instance.document_type in ['id_proof', 'degree_certificate', 'transcript']:
            send_user_notification.delay(
                user_id=instance.user.id,
                notification_type='document_uploaded',
                document_type=instance.get_document_type_display(),
            )


@receiver(pre_save, sender=WriterVerificationStatus)
def log_verification_state_changes(sender, instance, **kwargs):
    """Log verification state changes."""
    if instance.pk:
        try:
            old_instance = WriterVerificationStatus.objects.get(pk=instance.pk)
            
            if old_instance.state != instance.state:
                AuditLog.objects.create(
                    user=instance.user,
                    action_type='update',
                    model_name='WriterVerificationStatus',
                    object_id=str(instance.id),
                    changes={
                        'state': {'old': old_instance.state, 'new': instance.state}
                    },
                    before_state={'state': old_instance.state},
                    after_state={'state': instance.state},
                )
                
                # Send notification for state change
                if instance.state == 'approved':
                    send_user_notification.delay(
                        user_id=instance.user.id,
                        notification_type='writer_approved',
                        admin_name=instance.approved_by.get_full_name() if instance.approved_by else 'Admin',
                    )
                elif instance.state == 'rejected':
                    send_user_notification.delay(
                        user_id=instance.user.id,
                        notification_type='writer_rejected',
                        reason=instance.rejection_reason,
                    )
                elif instance.state == 'revision_required':
                    send_user_notification.delay(
                        user_id=instance.user.id,
                        notification_type='revision_required',
                        notes=instance.revision_notes,
                    )
        except WriterVerificationStatus.DoesNotExist:
            pass


@receiver(post_save, sender=ConsentLog)
def handle_consent_change(sender, instance, created, **kwargs):
    """Handle consent changes for GDPR compliance."""
    if created:
        # Update user model based on consent
        if instance.consent_type == ConsentLog.ConsentType.TERMS:
            instance.user.terms_accepted = instance.consent_given
            instance.user.save()
        elif instance.consent_type == ConsentLog.ConsentType.PRIVACY:
            instance.user.privacy_policy_accepted = instance.consent_given
            instance.user.save()
        elif instance.consent_type == ConsentLog.ConsentType.MARKETING:
            instance.user.marketing_emails = instance.consent_given
            instance.user.save()


@receiver(post_delete, sender=WriterDocument)
def delete_document_file(sender, instance, **kwargs):
    """Delete actual file when document record is deleted."""
    if instance.document:
        instance.document.delete(save=False)


@receiver(post_save, sender=WriterProfile)
def handle_writer_profile_completion(sender, instance, created, **kwargs):
    """Handle writer profile completion."""
    if not created and instance.profile_completed_at:
        # Check if this is the first time profile is completed
        old_instance = WriterProfile.objects.get(pk=instance.pk)
        if not old_instance.profile_completed_at and instance.profile_completed_at:
            # Log profile completion
            AuditLog.objects.create(
                user=instance.user,
                action_type='update',
                model_name='WriterProfile',
                object_id=str(instance.id),
                changes={'profile_completed': True},
            )
            
            # Update verification state if needed
            verification = instance.user.verification_status
            if verification.state == 'registered':
                verification.complete_profile()
                verification.save()