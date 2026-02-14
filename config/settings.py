"""
Django settings for media portfolio project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-change-me')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    # Jazzmin must be before django.contrib.admin
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'django_cleanup.apps.CleanupConfig',  # Auto-delete old files
    
    # Add these for task scheduling
    'django_celery_beat',
    'django_celery_results',
    
    # Local apps
    'media_portfolio.core',
    'media_portfolio.media',
    'media_portfolio.categories',
    'media_portfolio.comments',
    'media_portfolio.inquiries',
    'media_portfolio.collections',
    'media_portfolio.projects',  # Add this
    'media_portfolio.blog',       # Add this
    'media_portfolio.github',     # Add this
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'media_portfolio.core.context_processors.site_settings',
                'media_portfolio.core.context_processors.theme_preference',
                'media_portfolio.core.context_processors.global_stats',
                'media_portfolio.core.context_processors.latest_blog_posts',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
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

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Security settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True



# ============================================================================
# CELERY CONFIGURATION
# ============================================================================

CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULE = {
    'sync-github-repos': {
        'task': 'media_portfolio.github.tasks.sync_github_repos',
        'schedule': 86400.0,  # 24 hours
        'args': (os.getenv('GITHUB_USERNAME', ''),),
    },
    'sync-blog-posts': {
        'task': 'media_portfolio.blog.tasks.sync_blog_posts',
        'schedule': 21600.0,  # 6 hours
        'args': (os.getenv('DEVTO_USERNAME', ''),),
    },
}

# ============================================================================
# CACHING CONFIGURATION
# ============================================================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Cache timeout in seconds (24 hours)
CACHE_TTL = 60 * 60 * 24

# ============================================================================
# GITHUB API CONFIGURATION
# ============================================================================

GITHUB_USERNAME = os.getenv('GITHUB_USERNAME', '')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')  # Optional, for higher rate limits

# ============================================================================
# DEV.TO API CONFIGURATION
# ============================================================================

DEVTO_USERNAME = os.getenv('DEVTO_USERNAME', '')

# ============================================================================
# MEDIUM RSS CONFIGURATION
# ============================================================================

MEDIUM_USERNAME = os.getenv('MEDIUM_USERNAME', '')

# ============================================================================
# JAZZMIN CONFIGURATION - Professional Admin Theme with High Contrast Colors
# ============================================================================

JAZZMIN_SETTINGS = {
    # Title and branding
    "site_title": "Media Portfolio Admin",
    "site_header": "Media Portfolio",
    "site_brand": "MP Admin",
    "site_logo": None,  # Add path to your logo if available
    "login_logo": None,
    "login_logo_dark": None,
    "site_icon": None,
    "welcome_sign": "Welcome to Media Portfolio Administration",
    "copyright": "Media Portfolio © 2026",
    "search_model": ["auth.User", "media.MediaItem", "comments.Comment"],
    
    # User avatar
    "user_avatar": None,
    
    # Top Menu
    "topmenu_links": [
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "View Site", "url": "/", "new_window": True},
        {"name": "Media Gallery", "url": "/media/", "new_window": True},
        {"name": "Collections", "url": "/collections/", "new_window": True},
        {"app": "auth"},
        {"app": "media"},
    ],
    
    # User Menu
    "usermenu_links": [
        {"name": "Support", "url": "https://github.com/yourusername/media-portfolio/issues", "new_window": True},
        {"model": "auth.user"}
    ],
    
    # Side Menu
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    
    # Order of apps and models in the menu
    "order_with_respect_to": ["auth", "core", "media", "categories", "comments", "inquiries", "collections"],
    
    # Custom icons for apps and models
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.group": "fas fa-users",
        "core": "fas fa-home",
        "core.sitesettings": "fas fa-cog",
        "media": "fas fa-image",
        "media.mediaitem": "fas fa-film",
        "categories": "fas fa-folder-open",
        "categories.category": "fas fa-tags",
        "comments": "fas fa-comment",
        "comments.comment": "fas fa-comments",
        "comments.testimonial": "fas fa-star",
        "inquiries": "fas fa-envelope",
        "inquiries.inquiry": "fas fa-inbox",
        "collections": "fas fa-layer-group",
        "collections.collection": "fas fa-th-large",
    },
    
    # Default icons for parent/child menu items
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    
    # Related modal
    "related_modal_active": True,
    
    # Custom links to append to side menu
    "custom_links": {
        "media": [{
            "name": "Upload Media", 
            "url": "admin:media_mediaitem_add", 
            "icon": "fas fa-upload",
            "permissions": ["media.add_mediaitem"]
        }],
        "comments": [{
            "name": "Pending Moderation", 
            "url": "/admin/comments/comment/?is_approved__exact=0", 
            "icon": "fas fa-clock",
            "permissions": ["comments.change_comment"]
        }]
    },
    
    # UI Customizer - Enable if you want to customize via UI
    "show_ui_builder": False,
    
    # Change form formatting
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
        "media.mediaitem": "horizontal_tabs",
    },
}

# ============================================================================
# JAZZMIN UI THEME - High Contrast Professional Colors
# ============================================================================

JAZZMIN_UI_TWEAKS = {
    # Theme: Choose from available themes
    "theme": "darkly",  # Dark theme with high contrast
    
    # Color scheme
    "navbar": "navbar-dark",  # Options: navbar-dark, navbar-light
    "navbar_fixed": True,
    "navbar_color": "#1a1a2e",  # Deep midnight blue/purple
    
    # Sidebar
    "sidebar": "sidebar-dark-primary",
    "sidebar_fixed": True,
    "sidebar_color": "#16213e",  # Rich dark blue with purple undertones
    
    # Brand/text colors
    "brand_color": "#ffffff",  # White brand text
    "brand_small_text": False,
    "text_color": "#e9ecef",  # Light gray text
    "text_muted_color": "#adb5bd",  # Muted text color
    
    # Links - Purple/Blue gradient effect
    "link_color": "#9d4edd",  # Vibrant purple
    "link_hover_color": "#c77dff",  # Light purple on hover
    
    # Primary accent color (buttons, active items)
    "primary": "#6a4c9c",  # Royal purple
    "primary_hover": "#7d5fb0",  # Lighter purple on hover
    
    # Secondary accent
    "secondary": "#4a6fa5",  # Steel blue
    "secondary_hover": "#5d82b8",  # Lighter blue
    
    # Info/Success/Warning/Danger colors
    "info": "#3b8ea5",  # Teal blue
    "success": "#2a9d8f",  # Green-blue
    "warning": "#e9c46a",  # Warm yellow
    "danger": "#e76f51",  # Coral
    
    # Custom accent colors for specific elements
    "accent_blue": "#4361ee",  # Bright blue
    "accent_purple": "#9d4edd",  # Purple
    "accent_violet": "#7209b7",  # Deep violet
    "accent_indigo": "#3a0ca3",  # Indigo
    
    # Buttons
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
    
    # Tables
    "table_classes": "table table-striped table-hover",
    "table_striped": True,
    "table_hover": True,
    "table_bordered": False,
    "table_condensed": False,
    
    # Cards
    "card_border_radius": "8px",
    "card_shadow": "0 4px 12px rgba(106, 76, 156, 0.15)",  # Purple-tinted shadow
    "card_highlight": "#6a4c9c",  # Purple highlight for cards
    
    # Input fields
    "input_border_radius": "6px",
    "input_shadow": "inset 0 1px 3px rgba(0,0,0,0.1)",
    "input_focus_border": "#9d4edd",  # Purple focus border
    "input_focus_shadow": "0 0 0 3px rgba(157, 78, 221, 0.25)",  # Purple focus glow
    
    # Alerts
    "alert_border_radius": "8px",
    "alert_shadow": "0 2px 6px rgba(0,0,0,0.1)",
    
    # Dropdowns
    "dropdown_border_radius": "6px",
    "dropdown_shadow": "0 4px 12px rgba(0,0,0,0.2)",
    "dropdown_item_hover": "#6a4c9c",  # Purple hover for dropdown items
    "dropdown_item_hover_color": "#ffffff",  # White text on hover
    
    # Badges
    "badge_border_radius": "4px",
    "badge_primary_bg": "#6a4c9c",  # Purple badge background
    "badge_secondary_bg": "#4a6fa5",  # Blue badge background
    
    # Progress bars
    "progress_bar_primary": "#6a4c9c",  # Purple progress bar
    
    # List groups
    "list_group_active_bg": "#6a4c9c",  # Purple active list item
    "list_group_active_color": "#ffffff",  # White text on active
    
    # Action buttons
    "actions_sticky_top": True,
    
    # Dark mode toggle
    "dark_mode_theme": "cyborg",  # Optional dark mode theme
    
    # Custom CSS classes for specific elements
    "custom_css": """
        /* Custom purple/blue gradient for headers */
        .main-header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%) !important;
        }
        
        /* Purple glow for active menu items */
        .nav-sidebar .nav-item .nav-link.active {
            background: linear-gradient(90deg, #6a4c9c 0%, #4a6fa5 100%) !important;
            box-shadow: 0 2px 10px rgba(106, 76, 156, 0.3);
        }
        
        /* Blue hover effect for menu items */
        .nav-sidebar .nav-item .nav-link:hover {
            background: rgba(74, 111, 165, 0.2) !important;
        }
        
        /* Purple borders for cards */
        .card {
            border-top: 3px solid #6a4c9c !important;
        }
        
        /* Blue buttons */
        .btn-primary {
            background: linear-gradient(135deg, #6a4c9c 0%, #4a6fa5 100%) !important;
            border: none !important;
        }
        
        .btn-primary:hover {
            background: linear-gradient(135deg, #7d5fb0 0%, #5d82b8 100%) !important;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(106, 76, 156, 0.3);
        }
        
        /* Purple badges */
        .badge-primary {
            background: linear-gradient(135deg, #9d4edd 0%, #6a4c9c 100%) !important;
        }
        
        /* Blue badges */
        .badge-info {
            background: linear-gradient(135deg, #3a86ff 0%, #4a6fa5 100%) !important;
        }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: #1a1a2e;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #6a4c9c;
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #9d4edd;
        }
    """,
}
    
# Alternative HIGH CONTRAST themes you can try by changing "theme" above:
# "theme": "cyborg"     # High contrast dark theme with neon accents
# "theme": "darkly"     # Professional dark theme (current)
# "theme": "slate"      # Blue-gray dark theme
# "theme": "superhero"  # Navy blue theme with orange accents
# "theme": "materia"    # Material design with good contrast

# Remove or comment out the old SUIT_CONFIG since we're using Jazzmin now
# SUIT_CONFIG = { ... }