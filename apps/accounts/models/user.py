from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    """Custom manager for the User model."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user with an email and password."""
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model for EBWriting platform."""
    
    class UserType(models.TextChoices):
        CLIENT = 'client', _('Client')
        WRITER = 'writer', _('Writer')
        ADMIN = 'admin', _('Admin')
        MODERATOR = 'moderator', _('Moderator')
    
    email = models.EmailField(
        _('email address'),
        unique=True,
        db_index=True,
        help_text=_('Required. Must be a valid email address.')
    )
    
    user_type = models.CharField(
        _('user type'),
        max_length=20,
        choices=UserType.choices,
        default=UserType.CLIENT,
    )
    
    first_name = models.CharField(
        _('first name'),
        max_length=150,
        blank=True,
    )
    
    last_name = models.CharField(
        _('last name'),
        max_length=150,
        blank=True,
    )
    
    phone_number = models.CharField(
        _('phone number'),
        max_length=20,
        blank=True,
        null=True,
        help_text=_('International format (e.g., +1234567890)')
    )
    
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )
    
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    last_login = models.DateTimeField(_('last login'), blank=True, null=True)
    
    # GDPR compliance fields
    terms_accepted = models.BooleanField(
        _('terms accepted'),
        default=False,
        help_text=_('User has accepted the terms and conditions.')
    )
    
    privacy_policy_accepted = models.BooleanField(
        _('privacy policy accepted'),
        default=False,
        help_text=_('User has accepted the privacy policy.')
    )
    
    marketing_emails = models.BooleanField(
        _('marketing emails'),
        default=False,
        help_text=_('User has consented to marketing emails.')
    )
    
    data_anonymized = models.BooleanField(
        _('data anonymized'),
        default=False,
        help_text=_('User data has been anonymized for GDPR compliance.')
    )
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['user_type']),
            models.Index(fields=['date_joined']),
        ]
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        """Return the full name of the user."""
        full_name = f'{self.first_name} {self.last_name}'.strip()
        return full_name if full_name else self.email
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.email.split('@')[0]
    
    @property
    def is_client(self):
        return self.user_type == self.UserType.CLIENT
    
    @property
    def is_writer(self):
        return self.user_type == self.UserType.WRITER
    
    @property
    def is_admin_or_staff(self):
        return self.is_staff or self.user_type in [self.UserType.ADMIN, self.UserType.MODERATOR]
    
    def save(self, *args, **kwargs):
        # Normalize email before saving
        self.email = self.email.lower()
        super().save(*args, **kwargs)