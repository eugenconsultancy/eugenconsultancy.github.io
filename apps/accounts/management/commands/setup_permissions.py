from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Setup default groups and permissions for EBWriting platform'
    
    def handle(self, *args, **kwargs):
        self.stdout.write('Setting up default groups and permissions...')
        
        # Create groups
        groups = {
            'Clients': self._get_client_permissions(),
            'Writers': self._get_writer_permissions(),
            'Moderators': self._get_moderator_permissions(),
            'Administrators': self._get_admin_permissions(),
        }
        
        for group_name, permissions in groups.items():
            group, created = Group.objects.get_or_create(name=group_name)
            
            # Clear existing permissions
            group.permissions.clear()
            
            # Add new permissions
            for perm in permissions:
                group.permissions.add(perm)
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group: {group_name}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Updated group: {group_name}'))
        
        self.stdout.write(self.style.SUCCESS('Successfully setup groups and permissions'))
    
    def _get_client_permissions(self):
        """Get permissions for client users."""
        permissions = []
        
        # Order permissions
        content_type = ContentType.objects.get(app_label='orders', model='order')
        permissions.extend([
            Permission.objects.get(content_type=content_type, codename='add_order'),
            Permission.objects.get(content_type=content_type, codename='change_order'),
            Permission.objects.get(content_type=content_type, codename='view_order'),
        ])
        
        # Payment permissions
        content_type = ContentType.objects.get(app_label='payments', model='payment')
        permissions.extend([
            Permission.objects.get(content_type=content_type, codename='add_payment'),
            Permission.objects.get(content_type=content_type, codename='view_payment'),
        ])
        
        return permissions
    
    def _get_writer_permissions(self):
        """Get permissions for writer users."""
        permissions = self._get_client_permissions()  # Writers have client permissions too
        
        # Writer-specific permissions
        content_type = ContentType.objects.get(app_label='accounts', model='writerprofile')
        permissions.extend([
            Permission.objects.get(content_type=content_type, codename='change_writerprofile'),
            Permission.objects.get(content_type=content_type, codename='view_writerprofile'),
        ])
        
        # Order assignment permissions
        content_type = ContentType.objects.get(app_label='orders', model='order')
        permissions.append(
            Permission.objects.get(content_type=content_type, codename='change_order')  # For accepting assignments
        )
        
        return permissions
    
    def _get_moderator_permissions(self):
        """Get permissions for moderator users."""
        permissions = self._get_writer_permissions()  # Moderators have writer permissions
        
        # Admin view permissions
        apps = ['accounts', 'orders', 'payments', 'compliance']
        for app in apps:
            for model in ['user', 'writerprofile', 'order', 'payment', 'datarequest']:
                try:
                    content_type = ContentType.objects.get(app_label=app, model=model)
                    permissions.extend(
                        Permission.objects.filter(content_type=content_type, codename__startswith='view_')
                    )
                except ContentType.DoesNotExist:
                    continue
        
        return permissions
    
    def _get_admin_permissions(self):
        """Get permissions for administrator users."""
        # Admins get all permissions
        return Permission.objects.all()