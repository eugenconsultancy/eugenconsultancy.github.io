"""
Django settings for school_a project - RENDER DEPLOYMENT READY
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================
# SECURITY SETTINGS - PRODUCTION READY
# =============================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

# Parse ALLOWED_HOSTS from environment or use default for Render
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,.onrender.com').split(',')

# Render.com specific settings
RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# =============================================
# SECURITY MIDDLEWARE SETTINGS - PRODUCTION
# =============================================

# Security settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', 'https://*.onrender.com').split(',')

# Session settings
SESSION_COOKIE_AGE = 1209600  # 2 weeks in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# =============================================
# APPLICATION DEFINITION
# =============================================

INSTALLED_APPS = [
    # Core Django Unfold
    'unfold',
    
    # Django core apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'whitenoise.runserver_nostatic',  # For WhiteNoise
    
    # Your project apps
    'accounts',
    'students',
    'teachers',
    'marks',
    'payments',
    'school_messages',
]

MIDDLEWARE = [
    # Security middleware
    'django.middleware.security.SecurityMiddleware',
    
    # WhiteNoise for static files - MUST be here
    'whitenoise.middleware.WhiteNoiseMiddleware',
    
    # Session management
    'django.contrib.sessions.middleware.SessionMiddleware',
    
    # Common functionality
    'django.middleware.common.CommonMiddleware',
    
    # CSRF protection
    'django.middleware.csrf.CsrfViewMiddleware',
    
    # Authentication
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    
    # Messages framework
    'django.contrib.messages.middleware.MessageMiddleware',
    
    # Clickjacking protection
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'school_a.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'school_a.wsgi.application'

# =============================================
# DATABASE - POSTGRESQL FOR PRODUCTION
# =============================================

# Use DATABASE_URL from environment (set by Render)
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Production - PostgreSQL
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    # Development - SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# =============================================
# PASSWORD VALIDATION
# =============================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# =============================================
# INTERNATIONALIZATION
# =============================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.getenv('TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True

# =============================================
# STATIC & MEDIA FILES - WHITENOISE CONFIGURATION
# =============================================

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# =============================================
# DEFAULT PRIMARY KEY
# =============================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================
# AUTHENTICATION
# =============================================

AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# =============================================
# M-PESA CONFIGURATION (from environment)
# =============================================

MPESA_CONFIG = {
    'CONSUMER_KEY': os.getenv('MPESA_CONSUMER_KEY', ''),
    'CONSUMER_SECRET': os.getenv('MPESA_CONSUMER_SECRET', ''),
    'SHORTCODE': os.getenv('MPESA_SHORTCODE', ''),
    'PASSKEY': os.getenv('MPESA_PASSKEY', ''),
    'CALLBACK_URL': os.getenv('MPESA_CALLBACK_URL', ''),
    'ENVIRONMENT': os.getenv('MPESA_ENVIRONMENT', 'sandbox'),
}

# =============================================
# EMAIL CONFIGURATION
# =============================================

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

# =============================================
# DJANGO UNFOLD CONFIGURATION
# =============================================

UNFOLD = {
    "SITE_TITLE": os.getenv('UNFOLD_SITE_TITLE', 'School Admin System'),
    "SITE_HEADER": os.getenv('UNFOLD_SITE_HEADER', 'School Administration'),
    "SITE_URL": os.getenv('UNFOLD_SITE_URL', '/'),
    "SITE_SYMBOL": os.getenv('UNFOLD_SITE_SYMBOL', 'school'),
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    
    "STYLES": [
        "/static/css/unfold-custom.css",
        "/static/css/admin-overrides.css",
    ],
    
    "SCRIPTS": [
        "/static/js/unfold-custom.js",
    ],
    
    "COLORS": {
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "200": "233 213 255",
            "300": "216 180 254",
            "400": "192 132 252",
            "500": "168 85 247",
            "600": "147 51 234",
            "700": "126 34 206",
            "800": "107 33 168",
            "900": "88 28 135",
            "950": "59 7 100",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "Dashboard",
                "icon": "dashboard",
                "items": [
                    {
                        "title": "Admin Dashboard",
                        "icon": "dashboard",
                        "link": "/admin/",
                    },
                ],
            },
            {
                "title": "Users",
                "icon": "people",
                "items": [
                    {
                        "title": "Students",
                        "icon": "school",
                        "link": "/admin/students/student/",
                    },
                    {
                        "title": "Teachers",
                        "icon": "person",
                        "link": "/admin/teachers/teacher/",
                    },
                    {
                        "title": "Administrators",
                        "icon": "admin_panel_settings",
                        "link": "/admin/accounts/user/",
                    },
                ],
            },
            {
                "title": "Academic",
                "icon": "book",
                "items": [
                    {
                        "title": "Subjects",
                        "icon": "subject",
                        "link": "/admin/marks/subject/",
                    },
                    {
                        "title": "Marks",
                        "icon": "grade",
                        "link": "/admin/marks/mark/",
                    },
                    {
                        "title": "Student Reports",
                        "icon": "description",
                        "link": "/admin/marks/studentreport/",
                    },
                    {
                        "title": "Performance Trends",
                        "icon": "trending_up",
                        "link": "/admin/marks/performancetrend/",
                    },
                ],
            },
            {
                "title": "Financial",
                "icon": "payments",
                "items": [
                    {
                        "title": "Fee Payments",
                        "icon": "payment",
                        "link": "/admin/payments/payment/",
                    },
                    {
                        "title": "Fee Structures",
                        "icon": "request_quote",
                        "link": "/admin/payments/feestructure/",
                    },
                ],
            },
            {
                "title": "Communication",
                "icon": "message",
                "items": [
                    {
                        "title": "Messages",
                        "icon": "email",
                        "link": "/admin/school_messages/message/",
                    },
                    {
                        "title": "Holiday Notices",
                        "icon": "event",
                        "link": "/admin/school_messages/holidaynotice/",
                    },
                    {
                        "title": "Notifications",
                        "icon": "notifications",
                        "link": "/admin/school_messages/notification/",
                    },
                ],
            },
            {
                "title": "Analytics",
                "icon": "analytics",
                "items": [
                    {
                        "title": "Performance Analytics",
                        "icon": "trending_up",
                        "link": "/marks/analytics/student-performance/",
                        "permission": lambda request: request.user.is_staff,
                    },
                ],
            },
            {
                "title": "System",
                "icon": "settings",
                "items": [
                    {
                        "title": "Groups",
                        "icon": "group",
                        "link": "/admin/auth/group/",
                    },
                    {
                        "title": "Permissions",
                        "icon": "lock",
                        "link": "/admin/auth/permission/",
                    },
                ],
            },
        ],
    },
    "VERSION": "1.0.0",
}