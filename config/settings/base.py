"""
Django settings for EBWriting academic platform.

Generated using 'django-admin startproject' using Django 4.2.7.
"""

import os
from pathlib import Path
from datetime import timedelta
import environ

# 1. DEFINE BASE_DIR FIRST
# This points to the project root (usually 2 or 3 levels up from settings/base.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 2. Initialize environ
env = environ.Env()

# 3. Read .env file from the project root
env_file_path = BASE_DIR / '.env'

if os.path.exists(env_file_path):
    environ.Env.read_env(env_file_path)
else:
    # Try other possible locations safely
    possible_paths = [
        Path(__file__).resolve().parent.parent.parent.parent / '.env',  # 4 levels up
        BASE_DIR / '.env',
        '/etc/ebwriting/.env',  # Production location
    ]
    for path in possible_paths:
        if os.path.exists(path):
            environ.Env.read_env(path)
            break

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# Note: BASE_DIR is already defined above, removing duplicate definition

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env(
    'SECRET_KEY', 
    default='django-insecure-!@#dev-key-change-in-production!@#'
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=False)

# Determine environment
ENVIRONMENT = env('DJANGO_ENVIRONMENT', default='development').lower()
IS_PRODUCTION = ENVIRONMENT == 'production'
IS_STAGING = ENVIRONMENT == 'staging'
IS_DEVELOPMENT = ENVIRONMENT == 'development'

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# Application definition
INSTALLED_APPS = [
    # Django core apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required for allauth
    
    # Third party apps - Core
    # Authentication & Security
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'axes',
    'corsheaders',
    'auditlog',
    
    # Forms & UI
    'crispy_forms',
    'crispy_bootstrap5',
    'widget_tweaks',
    
    # Database & State Management
    'django_fsm',
    'django_fsm_log',
    'django_extensions',
    
    # Storage
    'storages',
    
    # API & Real-time (Phase 2)
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',
    'drf_yasg',
    'channels',
    'channels_redis',
    
    # Celery & Background Tasks (Phase 2)
    'django_celery_beat',
    'django_celery_results',
    
    # Email & Notifications (Phase 2)
    'django_htmx',
    
    # SEO & Content Management (Phase 5)
    'ckeditor',
    'ckeditor_uploader',
    'taggit',
    'import_export',
    
    # === PHASE 1: FOUNDATION, COMPLIANCE & TRUST ===
    # Core Platform - Note: Using AppConfig where available
    'apps.accounts',  # No apps.py found in your structure
    'apps.orders',    # No apps.py found in your structure
    'apps.payments',  # No apps.py found in your structure
    'apps.compliance',  # No apps.py found in your structure
    'apps.admin_tools',  # No apps.py found in your structure
    
    # === PHASE 2: COMMUNICATION & DELIVERY CONTROL ===
    # Communication & Notifications - Using AppConfig where available
    'apps.messaging',    # Has apps.py
    'apps.notifications',  # Has apps.py
    'apps.documents',    # Has apps.py
    
    # === PHASE 3: QUALITY, DISPUTES & API FOUNDATION ===
    # Using AppConfig classes
    'apps.revisions.apps.RevisionsConfig',
    'apps.plagiarism.apps.PlagiarismConfig',
    'apps.disputes.apps.DisputesConfig',
    'apps.api.apps.ApiConfig',
    
    # === PHASE 4: WRITER ECONOMY & ANALYTICS ===
    # Using AppConfig classes
    'apps.wallet.apps.WalletConfig',
    'apps.analytics.apps.AnalyticsConfig',
    'apps.reviews.apps.ReviewsConfig',
    
    # === PHASE 5: SEO & ASSISTIVE AI ===
    # Using AppConfig classes
    'apps.blog.apps.BlogConfig',
    'apps.ai_tools.apps.AIToolsConfig',
]

# Sites framework
SITE_ID = 1

MIDDLEWARE = [
    # Security middleware
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'csp.middleware.CSPMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    
    # Django core middleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    
    # Third party middleware
    'axes.middleware.AxesMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    
    # Custom middleware (Phase 1)
    # 'apps.compliance.middleware.GDPRComplianceMiddleware',  # Commented out if missing
    # 'apps.accounts.middleware.LastSeenMiddleware',  # Commented out if missing
]

ROOT_URLCONF = 'config.urls'

# Since this file is in config/settings/base.py, we go up THREE levels
# base.py (0) -> settings/ (1) -> config/ (2) -> academic_platform/ (3)
# BASE_DIR is already defined at the top, removing duplicate

# Your updated Templates configuration
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.i18n',
            ],
            'builtins': [
                'crispy_forms.templatetags.crispy_forms_tags',
                'crispy_forms.templatetags.crispy_forms_field',
            ],
        },
    },
]

# WSGI and ASGI configurations
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database Configuration
# This logic checks if a database URL exists in .env; if not, it uses SQLite.
if env.str('DATABASE_URL', default=''):
    DATABASES = {
        'default': env.db()
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': env('DB_ENGINE', default='django.db.backends.sqlite3'), # Fallback to sqlite3
            'NAME': env('DB_NAME', default=BASE_DIR / 'db.sqlite3'),
            'USER': env('DB_USER', default=''),
            'PASSWORD': env('DB_PASSWORD', default=''),
            'HOST': env('DB_HOST', default='localhost'),
            'PORT': env('DB_PORT', default=''),
        }
    }

# Password validation with strict security
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'OPTIONS': {
            'max_similarity': 0.7,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    # 'apps.accounts.validators.ComplexPasswordValidator',  # Commented out if missing
]

# Password hashers
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Locale paths
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Static files configuration
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
    # Removed non-existent directories to fix the warning
    # BASE_DIR / 'static' / 'css',
    # BASE_DIR / 'static' / 'js',
    # BASE_DIR / 'static' / 'images',
    # Removed fonts directory that doesn't exist
    # BASE_DIR / 'static' / 'fonts',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Static files finders
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Secure media settings
MEDIA_SECURE = env.bool('MEDIA_SECURE', default=False)
if MEDIA_SECURE:
    MEDIA_URL = '/secure-media/'
    MEDIA_ROOT = BASE_DIR / 'secure_media'

# Media folder structure - CORRECTED for your structure
MEDIA_SUBDIRECTORIES = {
    'writer_documents': 'writer_documents/{user_id}/',
    'order_files': 'order_files/{order_id}/',
    'message_attachments': 'message_attachments/{year}/{month}/{day}/',
    'generated_docs': 'generated_documents/{year}/{month}/{day}/',
    'profile_pictures': 'profile_pictures/{user_id}/',
    'document_templates': 'document_templates/',
    'blog_images': 'blog/images/{year}/{month}/',
    'ai_tools_outputs': 'ai_tools/outputs/{year}/{month}/',
}

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model - This MUST match your actual User model
# Note: Check your apps/accounts/apps.py for the label
# If no label is specified, use 'accounts.User'
AUTH_USER_MODEL = 'accounts.User'  # Updated to use 'accounts.User' since your app is registered as 'apps.accounts'

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth settings
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGIN_ATTEMPTS_LIMIT = 5
ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT = 300
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = True
ACCOUNT_PASSWORD_MIN_LENGTH = 12

# Login/Logout URLs
LOGIN_REDIRECT_URL = '/dashboard/'
LOGIN_URL = '/accounts/login/'
LOGOUT_REDIRECT_URL = '/'

# Crispy Forms configuration
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# Email Configuration
# Changed default to 'console' to prevent SMTP errors during local development
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@ebwriting.com')
SUPPORT_EMAIL = env('SUPPORT_EMAIL', default='support@ebwriting.com')
SERVER_EMAIL = env('SERVER_EMAIL', default='server@ebwriting.com')
EMAIL_TIMEOUT = 30

# Site information for templates
SITE_NAME = 'EBWriting'
SITE_URL = env('SITE_URL', default='https://ebwriting.com')
SITE_DOMAIN = env('SITE_DOMAIN', default='ebwriting.com')

# Security Settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'

# HTTPS settings
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=False)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=False)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 1209600
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# HSTS settings
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'", "https://cdn.jsdelivr.net")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net")
CSP_IMG_SRC = ("'self'", "data:", "https:", "blob:")
CSP_FONT_SRC = ("'self'", "https://cdn.jsdelivr.net")
CSP_CONNECT_SRC = ("'self'", "wss:", "ws:")
CSP_FRAME_SRC = ("'self'",)
CSP_MEDIA_SRC = ("'self'",)
CSP_OBJECT_SRC = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'",)
CSP_FRAME_ANCESTORS = ("'self'",)
CSP_REPORT_URI = ("/csp-violation-report/",)

# CORS settings
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Rate limiting with Axes
AXES_ENABLED = not DEBUG
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = 'accounts/auth/lockout.html'
# REMOVED DEPRECATED SETTING TO FIX WARNING
# AXES_META_PRECEDENCE_ORDER = [
#     'HTTP_X_FORWARDED_FOR',
#     'REMOTE_ADDR',
# ]
AXES_HANDLER = 'axes.handlers.database.AxesDatabaseHandler'
AXES_LOCKOUT_PARAMETERS = [["ip_address", "user_agent", "username"]]

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# ===== PHASE 1 SETTINGS =====
# Custom platform settings
WRITER_APPROVAL_REQUIRED = True
ESCROW_HOLD_PERIOD = 7
MAX_REVISION_COUNT = 3
PLATFORM_FEE_PERCENTAGE = 20
MINIMUM_ORDER_AMOUNT = 10.00
MAXIMUM_ORDER_AMOUNT = 10000.00
DEFAULT_CURRENCY = 'USD'

# Writer settings
WRITER_MINIMUM_RATING = 4.0
WRITER_MINIMUM_COMPLETION_RATE = 85
WRITER_MAX_CONCURRENT_ORDERS = 5
WRITER_DAILY_ORDER_LIMIT = 3

# Order settings
ORDER_EXPIRY_HOURS = 72
ORDER_REVISION_PERIOD = 7
ORDER_ESCROW_RELEASE_DELAY = 24
ORDER_AUTO_COMPLETE_DAYS = 14

# Payment settings
PAYMENT_HOLD_PERIOD = 7
MINIMUM_PAYOUT_AMOUNT = 50.00
PAYOUT_PROCESSING_DAYS = 3
REFUND_PROCESSING_DAYS = 5

# ===== PHASE 2 SETTINGS =====
# Notification settings
NOTIFICATION_DEFAULT_PREFERENCES = {
    'order_updates': {'email': True, 'push': True, 'sms': False},
    'messages': {'email': True, 'push': True, 'sms': False},
    'deadlines': {'email': True, 'push': True, 'sms': True},
    'payments': {'email': True, 'push': True, 'sms': False},
    'system': {'email': True, 'push': True, 'sms': False},
    'marketing': {'email': False, 'push': False, 'sms': False},
    'writer_updates': {'email': True, 'push': True, 'sms': False},
}

NOTIFICATION_QUIET_HOURS_START = '22:00'
NOTIFICATION_QUIET_HOURS_END = '08:00'
NOTIFICATION_DAILY_EMAIL_LIMIT = 20
NOTIFICATION_RETRY_ATTEMPTS = 3
NOTIFICATION_RETRY_DELAY = 300

# Messaging settings
MESSAGING_MAX_ATTACHMENTS_PER_MESSAGE = 5
MESSAGING_MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
MESSAGING_ALLOWED_FILE_TYPES = [
    'pdf', 'doc', 'docx', 'txt', 'rtf',
    'jpg', 'jpeg', 'png', 'gif',
    'xls', 'xlsx', 'ppt', 'pptx'
]
MESSAGING_MAX_MESSAGE_LENGTH = 5000
MESSAGING_RETENTION_DAYS = 365
MESSAGING_ADMIN_VISIBILITY = True

# Document generation settings
DOCUMENT_GENERATION_TIMEOUT = 30
DOCUMENT_MAX_FILE_SIZE = 10 * 1024 * 1024
DOCUMENT_ALLOWED_TEMPLATE_FORMATS = ['html', 'latex', 'docx']
DOCUMENT_DEFAULT_TEMPLATE = 'default'
DOCUMENT_SIGNATURE_REQUIRED = ['agreement', 'contract']
DOCUMENT_RETENTION_DAYS = 365 * 7

# PDF generation settings
WKHTMLTOPDF_PATH = env('WKHTMLTOPDF_PATH', default='/usr/local/bin/wkhtmltopdf')
PDFKIT_CONFIG = {
    'page-size': 'Letter',
    'encoding': 'UTF-8',
    'no-outline': None,
    'quiet': '',
    'margin-top': '0.75in',
    'margin-right': '0.75in',
    'margin-bottom': '0.75in',
    'margin-left': '0.75in',
}

# Virus scanning settings
CLAMAV_ENABLED = env.bool('CLAMAV_ENABLED', default=False)
CLAMAV_SOCKET = env('CLAMAV_SOCKET', default='/var/run/clamav/clamd.ctl')
CLAMAV_TIMEOUT = 30
CLAMAV_MAX_FILE_SIZE = 25 * 1024 * 1024

# ===== PHASE 3 SETTINGS =====
# Revisions settings
REVISION_SETTINGS = {
    'MAX_REVISIONS_PER_ORDER': 3,
    'REVISION_REQUEST_PERIOD': 7,
    'AUTO_ACCEPT_REVISION_DAYS': 3,
    'FREE_REVISIONS_INCLUDED': 1,
    'PAID_REVISION_RATE': 0.3,
    'REVISION_RESPONSE_DEADLINE': 72,
}

# Plagiarism settings
PLAGIARISM_SETTINGS = {
    'ENABLED': True,
    'REQUIRED_FOR_RELEASE': True,
    'ACCEPTABLE_THRESHOLD': 15,
    'SUSPICIOUS_THRESHOLD': 30,
    'UNACCEPTABLE_THRESHOLD': 50,
    'CHECK_TIMEOUT': 300,
    'API_KEYS': {
        'turnitin': env('TURNITIN_API_KEY', default=''),
        'copyleaks': env('COPYLEAKS_API_KEY', default=''),
        'grammarly': env('GRAMMARLY_API_KEY', default=''),
    },
    'EXCLUDE_SOURCES': ['wikipedia', 'project_gutenberg', 'standard_texts'],
}

# Disputes settings
DISPUTE_SETTINGS = {
    'RESPONSE_DEADLINE_HOURS': 72,
    'ESCALATION_THRESHOLD': 3,
    'AUTO_RESOLUTION_DAYS': 14,
    'REFUND_TRIGGER_THRESHOLD': 80,
    'DISPUTE_FEE_PERCENTAGE': 10,
    'MINIMUM_DISPUTE_AMOUNT': 20.00,
    'MAX_CONCURRENT_DISPUTES': 3,
}

# API settings
API_SETTINGS = {
    'DEFAULT_VERSION': 'v1',
    'VERSIONS': ['v1', 'v2'],
    'RATE_LIMIT_PER_USER': '1000/day',
    'RATE_LIMIT_PER_IP': '100/day',
    'API_KEY_REQUIRED_FOR': ['orders', 'payments', 'documents'],
    'ALLOWED_ORIGINS': env.list('API_ALLOWED_ORIGINS', default=[]),
    'WEBHOOK_SECRET': env('WEBHOOK_SECRET', default=''),
    'WEBHOOK_TIMEOUT': 10,
}

# ===== PHASE 4 SETTINGS =====
# Wallet settings
WALLET_SETTINGS = {
    'MINIMUM_PAYOUT_THRESHOLD': 50.00,
    'DEFAULT_COMMISSION_RATE': 20.00,
    'PAYOUT_METHODS': [
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer'),
        ('skrill', 'Skrill'),
        ('payoneer', 'Payoneer'),
    ],
    'PAYOUT_PROCESSING_DAYS': 3,
    'DAILY_WITHDRAWAL_LIMIT': 1000.00,
    'MONTHLY_WITHDRAWAL_LIMIT': 10000.00,
    'WITHDRAWAL_FEE_PERCENTAGE': 2.5,
    'MINIMUM_DEPOSIT_AMOUNT': 10.00,
    'MAXIMUM_DEPOSIT_AMOUNT': 5000.00,
    'ESCROW_HOLD_PERIOD': 7,
}

# Reviews settings
REVIEW_SETTINGS = {
    'AUTO_APPROVE_RATING_THRESHOLD': 3,
    'FLAG_THRESHOLD': 3,
    'LOW_RATING_THRESHOLD': 3.0,
    'MIN_REVIEWS_FOR_RESTRICTION': 5,
    'MODERATION_REQUIRED_RATING': 2,
    'MIN_WORDS_FOR_REVIEW': 10,
    'MAX_WORDS_FOR_REVIEW': 500,
    'COOLDOWN_PERIOD_HOURS': 24,
    'REVIEW_EXPIRY_DAYS': 30,
    'AVERAGE_RATING_CALCULATION': 'weighted',
}

# Analytics settings
ANALYTICS_SETTINGS = {
    'KPI_CALCULATION_INTERVAL': 86400,
    'REPORT_RETENTION_DAYS': 365,
    'DASHBOARD_REFRESH_INTERVAL': 300,
    'PERFORMANCE_REPORT_PERIODS': {
        '7d': 'Last 7 Days',
        '30d': 'Last 30 Days',
        '90d': 'Last 90 Days',
        '180d': 'Last 180 Days',
        '365d': 'Last Year',
    },
    'KPI_METRICS': {
        'writer_approval_rate': {'target': 85, 'min': 70},
        'order_completion_rate': {'target': 95, 'min': 85},
        'average_delivery_time': {'target': 48, 'max': 72},
        'customer_satisfaction': {'target': 4.5, 'min': 4.0},
        'refund_rate': {'target': 2, 'max': 5},
        'revenue_growth': {'target': 10, 'min': 5},
    },
    'DATA_PRIVACY': {
        'ANONYMIZE_AFTER_DAYS': 90,
        'DELETE_AFTER_DAYS': 365,
        'AGGREGATE_DATA_ONLY': True,
    },
}

# ===== PHASE 5 SETTINGS =====
# CKEditor Configuration
CKEDITOR_UPLOAD_PATH = "uploads/ckeditor/"
CKEDITOR_IMAGE_BACKEND = "pillow"
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'Custom',
        'toolbar_Custom': [
            ['Bold', 'Italic', 'Underline', 'Strike'],
            ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 
             'JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock'],
            ['Link', 'Unlink', 'Anchor'],
            ['Image', 'Table', 'HorizontalRule', 'SpecialChar'],
            ['Format', 'Font', 'FontSize'],
            ['TextColor', 'BGColor'],
            ['Maximize', 'ShowBlocks'],
            ['Source']
        ],
        'height': 300,
        'width': '100%',
        'filebrowserUploadUrl': '/ckeditor/upload/',
        'filebrowserBrowseUrl': '/ckeditor/browse/',
    },
}

# Blog settings
BLOG_SETTINGS = {
    'POSTS_PER_PAGE': 10,
    'FEATURED_POSTS_COUNT': 3,
    'POPULAR_POSTS_COUNT': 5,
    'EXCERPT_LENGTH': 300,
    'COMMENTS_PER_PAGE': 20,
    'AUTO_APPROVE_COMMENTS': False,
    'ALLOW_GUEST_COMMENTS': True,
    'COMMENT_MIN_LENGTH': 10,
    'COMMENT_MAX_LENGTH': 1000,
    'SUBSCRIBER_COOLDOWN_HOURS': 24,
    'SEO_AUDIT_ENABLED': True,
    'SITEMAP_CACHE_TIMEOUT': 86400,
    'RSS_FEED_ITEMS': 20,
}

# AI Tools settings
AI_TOOLS_SETTINGS = {
    'ENABLED': True,
    'DISCLAIMER_REQUIRED': True,
    'LOG_ALL_USAGE': True,
    'REVIEW_REQUIRED': False,
    'MAX_INPUT_LENGTH': 5000,
    'MAX_OUTPUT_LENGTH': 2000,
    'DAILY_LIMITS': {
        'outline_helper': 10,
        'grammar_checker': 20,
        'citation_formatter': 15,
        'paraphrasing_tool': 10,
        'thesis_generator': 5,
    },
    'CONTENT_FILTERS': {
        'ENABLED': True,
        'BLOCKED_TERMS': ['cheat', 'plagiarize', 'buy essay', 'academic dishonesty'],
        'REQUIRE_HUMAN_REVIEW': True,
    },
    'PRIVACY': {
        'RETAIN_INPUT_TEXT': True,
        'RETAIN_OUTPUT_TEXT': True,
        'RETENTION_DAYS': 90,
        'ANONYMIZE_AFTER_DAYS': 30,
    },
}

# SEO settings
SEO_SETTINGS = {
    'META_DESCRIPTION_LENGTH': 160,
    'META_TITLE_LENGTH': 60,
    'OPEN_GRAPH_ENABLED': True,
    'TWITTER_CARDS_ENABLED': True,
    'SCHEMA_MARKUP_ENABLED': True,
    'SITEMAP_PRIORITIES': {
        'home': 1.0,
        'blog_home': 0.9,
        'blog_post': 0.8,
        'blog_category': 0.7,
        'static_pages': 0.5,
    },
    'CANONICAL_URL_ENABLED': True,
    'ROBOTS_TXT': env('ROBOTS_TXT_CONTENT', default=''),
}

# Audit logging
AUDITLOG_INCLUDE_ALL_MODELS = True
AUDITLOG_EXCLUDE_TRACKING_MODELS = [
    'sessions.Session',
    'admin.LogEntry',
    'contenttypes.ContentType',
    'auditlog.LogEntry',
]
AUDITLOG_CREATE = True
AUDITLOG_UPDATE = True
AUDITLOG_DELETE = True
AUDITLOG_ACCESS = True

# Logs directory
LOGS_DIR = BASE_DIR / 'logs'
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Logging configuration - SIMPLIFIED to match your structure
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'django.log',
            'maxBytes': 1024 * 1024 * 100,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file', 'mail_admins'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['file', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
        # Root logger for all apps
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Channels configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(
                env('REDIS_HOST', default='localhost'),
                env.int('REDIS_PORT', default=6379)
            )],
            'capacity': 1500,
            'expiry': 10,
        },
    },
}

# WebSocket settings
WEBSOCKET_URL = '/ws/'
WEBSOCKET_HEARTBEAT_INTERVAL = 30
WEBSOCKET_HEARTBEAT_TIMEOUT = 60
WEBSOCKET_MAX_CONNECTIONS = 1000

# Celery configuration
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Celery beat schedule - UPDATED with correct task paths
CELERY_BEAT_SCHEDULE = {
    # Commented out missing tasks
    # 'cleanup-old-notifications': {
    #     'task': 'apps.notifications.tasks.cleanup_old_notifications',
    #     'schedule': timedelta(days=1),
    #     'args': (90,),
    # },
    # 'check-order-deadlines': {
    #     'task': 'apps.orders.tasks.check_order_deadlines',
    #     'schedule': timedelta(hours=6),
    # },
    # 'process-pending-payouts': {
    #     'task': 'apps.payments.tasks.process_pending_payouts',
    #     'schedule': timedelta(days=1),
    # },
}

# Django REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# JWT settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# Cache configuration
# Updated to LocMemCache for local development to avoid Redis connection errors
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',  # A unique name for this cache instance
        'KEY_PREFIX': 'ebwriting',
    },
}

# Session engine
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'

# Test settings
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# Fixtures
FIXTURE_DIRS = [
    BASE_DIR / 'fixtures',
]

# Custom settings validator
def validate_settings():
    """Validate critical settings."""
    errors = []
    
    is_production = IS_PRODUCTION or IS_STAGING

    if is_production and (SECRET_KEY.startswith('django-insecure-') or 
                         len(SECRET_KEY) < 50):
        errors.append("SECRET_KEY must be secure in production")
    
    if is_production and DEBUG:
        errors.append("DEBUG should be False in production")
    
    if is_production and DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
        errors.append("Use PostgreSQL in production")
    
    if errors:
        raise RuntimeError(f"Settings validation failed: {', '.join(errors)}")

# Run validation
validate_settings()