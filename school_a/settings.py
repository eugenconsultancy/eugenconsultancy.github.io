"""
Django settings for school_a project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =============================================
# SECURITY SETTINGS
# =============================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    'SECRET_KEY', 
    'django-insecure-your-secret-key-here'
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')

# Parse ALLOWED_HOSTS from comma-separated string
allowed_hosts_str = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_str.split(',') if host.strip()]

# =============================================
# SECURITY MIDDLEWARE SETTINGS
# =============================================

# Security settings based on DEBUG mode
CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'False').lower() in ('true', '1', 't')
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1', 't')
SESSION_COOKIE_HTTPONLY = True

# Parse CSRF_TRUSTED_ORIGINS from environment variable
csrf_origins_str = os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins_str.split(',') if origin.strip()]

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
    
    # Your project apps (CORRECTED - without .Config)
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
    
    # WhiteNoise for static files (optional - uncomment if using)
    # 'whitenoise.middleware.WhiteNoiseMiddleware',
    
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
# DATABASE
# =============================================

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
# STATIC & MEDIA FILES
# =============================================

STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

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
    'CONSUMER_KEY': os.getenv('MPESA_CONSUMER_KEY', 'your_consumer_key_here'),
    'CONSUMER_SECRET': os.getenv('MPESA_CONSUMER_SECRET', 'your_consumer_secret_here'),
    'SHORTCODE': os.getenv('MPESA_SHORTCODE', 'your_shortcode_here'),
    'PASSKEY': os.getenv('MPESA_PASSKEY', 'your_passkey_here'),
    'CALLBACK_URL': os.getenv('MPESA_CALLBACK_URL', 'https://yourdomain.com/payments/mpesa-callback/'),
    'ENVIRONMENT': os.getenv('MPESA_ENVIRONMENT', 'sandbox'),  # 'sandbox' or 'production'
}

# =============================================
# EMAIL CONFIGURATION
# =============================================

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 25))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False').lower() in ('true', '1', 't')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

# =============================================
# DJANGO UNFOLD CONFIGURATION - FIXED
# =============================================

UNFOLD = {
    "SITE_TITLE": os.getenv('UNFOLD_SITE_TITLE', 'School Admin System'),
    "SITE_HEADER": os.getenv('UNFOLD_SITE_HEADER', 'School Administration'),
    "SITE_URL": os.getenv('UNFOLD_SITE_URL', '/'),
    "SITE_SYMBOL": os.getenv('UNFOLD_SITE_SYMBOL', 'school'),
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    
    # Custom CSS stylesheets
    "STYLES": [
        "/static/css/unfold-custom.css",  # Primary custom styles
        "/static/css/admin-overrides.css",  # Additional overrides
    ],
    
    # Custom JavaScript files
    "SCRIPTS": [
        "/static/js/unfold-custom.js",  # Custom JavaScript functionality
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
                "items": [  # FIXED: Changed from "link" to "items" array
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
                "items": [  # FIXED: Changed from "link" to "items" array
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
    
    # Version information
    "VERSION": "1.0.0",
    
    # REMOVE or COMMENT OUT TABS - it's causing conflicts
    # "TABS": [
    #     {
    #         "models": [
    #             "accounts.user",
    #             "auth.group",
    #         ],
    #         "items": [
    #             {
    #                 "title": "Users",
    #                 "link": "/admin/accounts/user/",
    #             },
    #             {
    #                 "title": "Groups",
    #                 "link": "/admin/auth/group/",
    #             },
    #         ],
    #     },
    # ],
}