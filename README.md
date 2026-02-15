I'll provide all the necessary files and commands to deploy your Django portfolio project to Heroku. This includes configuration files, production settings, and deployment commands.

## 📁 Deployment Files

### File: requirements.txt (Complete Production Requirements)
```bash
# Create/update requirements.txt
```

```txt
# Core Django
Django==4.2.7
gunicorn==21.2.0
whitenoise==6.6.0
dj-database-url==2.1.0
python-dotenv==1.0.0

# Database
psycopg2-binary==2.9.9

# Media/Image Processing
Pillow==10.1.0
django-cleanup==7.0.0
django-cloudinary-storage==0.3.0
cloudinary==1.36.0

# AWS S3 (Alternative to Cloudinary)
boto3==1.34.0
django-storages==1.14.2

# Email
django-smtp-ssl==1.0

# Security
django-cors-headers==4.3.1

# Admin & UI
django-ckeditor==6.7.0
django-jet-reboot==1.3.0

# Performance
django-compressor==4.4
django-redis==5.4.0
redis==5.0.1

# Monitoring
sentry-sdk==1.40.0

# Utilities
django-allauth==0.58.2  # For social auth (optional)
django-countries==7.5.1
```

### File: runtime.txt (Python Version)
```bash
touch runtime.txt
```

```txt
python-3.11.7
```

### File: Procfile (Heroku Process Configuration)
```bash
touch Procfile
```

```txt
web: gunicorn config.wsgi:application --log-file -
release: python manage.py migrate --noinput
```

### File: Procfile.windows (For Windows Testing)
```bash
touch Procfile.windows
```

```txt
web: python manage.py runserver 0.0.0.0:8000
```

### File: app.json (Heroku App Configuration)
```bash
touch app.json
```

```json
{
  "name": "Media Portfolio",
  "description": "Professional photography and videography portfolio website",
  "repository": "https://github.com/yourusername/media-portfolio",
  "keywords": ["django", "portfolio", "photography", "bootstrap"],
  "env": {
    "SECRET_KEY": {
      "description": "A secret key for verifying the integrity of signed cookies.",
      "generator": "secret"
    },
    "DJANGO_SETTINGS_MODULE": {
      "description": "Django settings module",
      "value": "config.settings_production"
    },
    "DEBUG": {
      "description": "Debug mode",
      "value": "False"
    },
    "ALLOWED_HOSTS": {
      "description": "Allowed hosts",
      "value": ".herokuapp.com"
    }
  },
  "formation": {
    "web": {
      "quantity": 1,
      "size": "eco"
    }
  },
  "addons": [
    {
      "plan": "heroku-postgresql:mini"
    },
    {
      "plan": "heroku-redis:mini"
    },
    {
      "plan": "cloudinary:starter"
    }
  ],
  "buildpacks": [
    {
      "url": "heroku/python"
    }
  ],
  "environments": {
    "test": {
      "scripts": {
        "test": "python manage.py test"
      }
    }
  }
}
```

### File: config/settings_production.py
```bash
touch config/settings_production.py
```

```python
"""
Production settings for Heroku deployment
"""
import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', os.getenv('SECRET_KEY'))

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '.herokuapp.com,localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',  # Whitenoise for static files
    'django.contrib.staticfiles',
    
    # Third-party apps
    'django_cleanup',
    'cloudinary_storage',
    'cloudinary',
    'storages',
    'corsheaders',
    'django_compressor',
    
    # Local apps
    'media_portfolio.core',
    'media_portfolio.categories',
    'media_portfolio.media',
    'media_portfolio.comments',
    'media_portfolio.inquiries',
    'media_portfolio.collections',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Whitenoise for static files
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
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database - Use PostgreSQL on Heroku
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', 'sqlite:///db.sqlite3'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files - Using Cloudinary
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', os.getenv('CLOUDINARY_CLOUD_NAME')),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY', os.getenv('CLOUDINARY_API_KEY')),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', os.getenv('CLOUDINARY_API_SECRET')),
}

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Alternative: AWS S3 Storage (uncomment if using S3 instead of Cloudinary)
# AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
# AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
# AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
# AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
# AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
# AWS_S3_FILE_OVERWRITE = False
# AWS_DEFAULT_ACL = 'public-read'
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# Media URL
MEDIA_URL = '/media/'  # Fallback for local development

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Security Settings
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True') == 'True'
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True') == 'True'
CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'True') == 'True'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# CORS Settings
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', 'https://*.herokuapp.com').split(',')
CORS_ALLOW_CREDENTIALS = True

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'https://*.herokuapp.com').split(',')

# Email Settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@example.com')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')

# Redis Cache (for performance)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_CLASS': 'redis.connection.BlockingConnectionPool',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'timeout': 20,
            },
            'PARSER_CLASS': 'redis.connection.HiredisParser',
        },
        'KEY_PREFIX': 'portfolio',
        'TIMEOUT': 300,  # 5 minutes
    }
}

# Session cache
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

# Sentry for error tracking (optional)
if os.environ.get('SENTRY_DSN'):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    
    sentry_sdk.init(
        dsn=os.environ.get('SENTRY_DSN'),
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=True,
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
    )
```

### File: .env.production (Environment Variables Template)
```bash
touch .env.production
```

```env
# Django Settings
SECRET_KEY=your-strong-secret-key-here-change-in-production
DEBUG=False
ALLOWED_HOSTS=.herokuapp.com,localhost,127.0.0.1,yourdomain.com
DJANGO_SETTINGS_MODULE=config.settings_production

# Database
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Cloudinary Settings
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret

# AWS S3 (Alternative)
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=us-east-1

# Email Settings
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
ADMIN_EMAIL=admin@yourdomain.com

# Redis URL (provided by Heroku)
REDIS_URL=redis://:password@host:port

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Sentry (optional)
SENTRY_DSN=your-sentry-dsn
SENTRY_ENVIRONMENT=production

# Site URL for emails
BASE_URL=https://yourdomain.com
```

### File: .gitignore (Updated)
```bash
# Update .gitignore with production exclusions
```

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Django
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal
media/
staticfiles/
/media/
static/

# Environment
.env
.env.local
.env.production
.env.staging

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Heroku
Procfile.windows

# Deployment
config/settings_local.py
```

### File: runtime.txt (Python Version)
```bash
touch runtime.txt
```

```txt
python-3.11.7
```

### File: .buildpacks (Optional - Custom Buildpacks)
```bash
touch .buildpacks
```

```txt
https://github.com/heroku/heroku-buildpack-python.git
```

### File: bin/post_compile (Post-Compile Script)
```bash
mkdir -p bin
touch bin/post_compile
chmod +x bin/post_compile
```

```bash
#!/usr/bin/env bash
echo "Running post_compile script..."

# Run database migrations
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Create cache table
python manage.py createcachetable

# Compress assets
python manage.py compress --force

echo "Post_compile script completed!"
```

### File: gunicorn.conf.py (Gunicorn Configuration)
```bash
touch gunicorn.conf.py
```

```python
"""
Gunicorn configuration file
"""
import multiprocessing
import os

# Bind to host and port
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 30
graceful_timeout = 30
keepalive = 2

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = 'portfolio'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = 'path/to/keyfile'
# certfile = 'path/to/certfile'

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
```

## 📋 Deployment Commands

### Step 1: Initialize Git Repository
```bash
# Initialize git if not already done
git init

# Add all files
git add .

# Commit files
git commit -m "Initial commit for Heroku deployment"
```

### Step 2: Install Heroku CLI
```bash
# Download and install Heroku CLI from: https://devcenter.heroku.com/articles/heroku-cli

# Verify installation
heroku --version

# Login to Heroku
heroku login
```

### Step 3: Create Heroku App
```bash
# Create a new Heroku app
heroku create your-portfolio-app-name

# Or create with specific region
heroku create your-portfolio-app-name --region us

# Rename app if needed
heroku apps:rename new-name
```

### Step 4: Add Heroku Add-ons
```bash
# Add PostgreSQL database
heroku addons:create heroku-postgresql:mini

# Add Redis for caching
heroku addons:create heroku-redis:mini

# Add Cloudinary for media storage
heroku addons:create cloudinary:starter

# Optional: Add Sentry for error tracking
heroku addons:create sentry:f1
```

### Step 5: Set Environment Variables
```bash
# Set Django secret key
heroku config:set SECRET_KEY="your-very-strong-secret-key-here"

# Set Django settings module
heroku config:set DJANGO_SETTINGS_MODULE=config.settings_production

# Set allowed hosts
heroku config:set ALLOWED_HOSTS=".herokuapp.com,yourdomain.com"

# Set debug mode
heroku config:set DEBUG=False

# Set email settings (using Gmail example)
heroku config:set EMAIL_HOST=smtp.gmail.com
heroku config:set EMAIL_PORT=587
heroku config:set EMAIL_USE_TLS=True
heroku config:set EMAIL_HOST_USER=your-email@gmail.com
heroku config:set EMAIL_HOST_PASSWORD="your-app-specific-password"
heroku config:set DEFAULT_FROM_EMAIL=noreply@yourdomain.com
heroku config:set ADMIN_EMAIL=admin@yourdomain.com

# Set security settings
heroku config:set SECURE_SSL_REDIRECT=True
heroku config:set SESSION_COOKIE_SECURE=True
heroku config:set CSRF_COOKIE_SECURE=True
heroku config:set CORS_ALLOWED_ORIGINS="https://yourdomain.com,https://www.yourdomain.com"
heroku config:set CSRF_TRUSTED_ORIGINS="https://yourdomain.com,https://www.yourdomain.com"

# Set site URL
heroku config:set BASE_URL=https://yourdomain.com
```

### Step 6: Configure Cloudinary (if not using addon)
```bash
# If you didn't use the addon, set Cloudinary credentials manually
heroku config:set CLOUDINARY_CLOUD_NAME=your-cloud-name
heroku config:set CLOUDINARY_API_KEY=your-api-key
heroku config:set CLOUDINARY_API_SECRET=your-api-secret
```

### Step 7: Deploy to Heroku
```bash
# Push code to Heroku
git push heroku main

# If you're using a different branch
git push heroku your-branch:main
```

### Step 8: Run Database Migrations
```bash
# Run migrations on Heroku
heroku run python manage.py migrate

# Create superuser
heroku run python manage.py createsuperuser

# Create initial site settings
heroku run python manage.py shell -c "from media_portfolio.core.models import SiteSettings; SiteSettings.objects.create(site_title='My Media Portfolio', site_description='Professional photography and videography portfolio', contact_email='admin@example.com', copyright_text='© 2025 All Rights Reserved')"
```

### Step 9: Open the App
```bash
# Open the app in browser
heroku open
```

### Step 10: Set up Custom Domain (Optional)
```bash
# Add custom domain
heroku domains:add www.yourdomain.com

# Add without www
heroku domains:add yourdomain.com

# Check domains
heroku domains

# Configure DNS with your provider (add CNAME record pointing to your-app-name.herokuapp.com)
```

### Step 11: Enable SSL (Optional)
```bash
# Automated Certificate Management (free)
heroku certs:auto:enable
```

## 🔧 Useful Heroku Commands

### Monitoring and Debugging
```bash
# View logs
heroku logs --tail

# View specific log lines
heroku logs -n 100

# Run one-off commands
heroku run python manage.py shell
heroku run python manage.py dbshell

# Check app status
heroku ps

# Restart app
heroku restart

# Scale dynos
heroku ps:scale web=1

# Check config variables
heroku config

# View PostgreSQL info
heroku pg:info

# Backup database
heroku pg:backups:capture
heroku pg:backups:download
```

### Maintenance Mode
```bash
# Enable maintenance mode
heroku maintenance:on

# Disable maintenance mode
heroku maintenance:off

# Run migrations during maintenance
heroku maintenance:on
heroku run python manage.py migrate
heroku maintenance:off
```

### Rollback
```bash
# Rollback to previous release
heroku releases
heroku rollback v42
```

## 📝 Additional Configuration Files

### File: .editorconfig
```bash
touch .editorconfig
```

```ini
# EditorConfig helps maintain consistent coding styles
root = true

[*]
end_of_line = lf
insert_final_newline = true
charset = utf-8
indent_style = space
indent_size = 4
trim_trailing_whitespace = true

[*.{html,js,json,yml,yaml}]
indent_size = 2

[*.md]
trim_trailing_whitespace = false
```

### File: .slugignore (Files to exclude from Heroku slug)
```bash
touch .slugignore
```

```txt
# Ignore development files in deployment
.git
.github
.gitignore
README.md
TODO.md
.env
.env.local
.env.production
*.pyc
__pycache__/
venv/
env/
ENV/
.vscode/
.idea/
*.db
*.sqlite3
staticfiles/
media/
tests/
docs/
examples/
```

### File: Makefile (For easier deployment)
```bash
touch Makefile
```

```makefile
.PHONY: help install migrate collectstatic deploy logs shell test backup

help:
	@echo "Available commands:"
	@echo "  install      - Install dependencies"
	@echo "  migrate      - Run database migrations"
	@echo "  collectstatic- Collect static files"
	@echo "  deploy       - Deploy to Heroku"
	@echo "  logs         - View Heroku logs"
	@echo "  shell        - Open Django shell on Heroku"
	@echo "  test         - Run tests"
	@echo "  backup       - Backup database"

install:
	pip install -r requirements.txt

migrate:
	heroku run python manage.py migrate

collectstatic:
	python manage.py collectstatic --noinput

deploy:
	git push heroku main
	heroku run python manage.py migrate
	heroku open

logs:
	heroku logs --tail

shell:
	heroku run python manage.py shell

test:
	python manage.py test

backup:
	heroku pg:backups:capture
	heroku pg:backups:download

rollback:
	@echo "Recent releases:"
	heroku releases
	@read -p "Enter release version to rollback to: " version; \
	heroku rollback $$version

maintenance-on:
	heroku maintenance:on

maintenance-off:
	heroku maintenance:off
```

## 🚀 Quick Deployment Checklist

```bash
# 1. Prepare your project
python manage.py check --deploy
python manage.py test

# 2. Initialize git
git init
git add .
git commit -m "Ready for deployment"

# 3. Create Heroku app
heroku create your-app-name

# 4. Add addons
heroku addons:create heroku-postgresql:mini
heroku addons:create heroku-redis:mini
heroku addons:create cloudinary:starter

# 5. Set environment variables
heroku config:set SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(50))")
heroku config:set DJANGO_SETTINGS_MODULE=config.settings_production
heroku config:set DEBUG=False
heroku config:set ALLOWED_HOSTS=".herokuapp.com"

# 6. Deploy
git push heroku main

# 7. Setup database
heroku run python manage.py migrate
heroku run python manage.py createsuperuser

# 8. Open app
heroku open
```

## 🔐 Security Checklist for Production

```python
# Run this in Django shell to verify security settings
python manage.py check --deploy
```

Your Django portfolio project is now ready for production deployment on Heroku with all necessary configuration files and deployment commands!









FROM 1000 HERE UPDATE FOR JAZZMIN: 

I'll update your settings file to include django-jazzmin for an enhanced admin interface without altering any existing configuration:

### File: config/settings.py (Updated with Jazzmin)

```python
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

# Application definition
INSTALLED_APPS = [
    # Jazzmin - Must be before django.contrib.admin
    'jazzmin',
    
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'django_cleanup.apps.CleanupConfig',  # Auto-delete old files
    
    # Local apps
    'media_portfolio.core',
    'media_portfolio.media',
    'media_portfolio.categories',
    'media_portfolio.comments',
    'media_portfolio.inquiries',
    'media_portfolio.collections',
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
# JAZZMIN ADMIN CONFIGURATION
# ============================================================================

JAZZMIN_SETTINGS = {
    # Title of the window
    'site_title': 'Media Portfolio Admin',
    
    # Title on the login screen
    'site_header': 'Portfolio Management',
    
    # Title on the brand
    'site_brand': 'Media Portfolio',
    
    # Logo to use for your site (must be in static files)
    'site_logo': 'images/logo.png',
    
    # Logo to use for login form
    'login_logo': None,
    
    # Logo for dark mode
    'site_logo_classes': 'img-circle',
    
    # Welcome text on the login screen
    'welcome_sign': 'Welcome to the Portfolio Admin Panel',
    
    # Copyright on the footer
    'copyright': 'Media Portfolio',
    
    # The model admin to search from the search bar
    'search_model': ['media.MediaItem', 'categories.Category'],
    
    # Field name on user model that contains avatar image
    'user_avatar': None,
    
    ############
    # Top Menu #
    ############
    'topmenu_links': [
        {'name': 'Home', 'url': 'admin:index', 'permissions': ['auth.view_user']},
        {'name': 'View Site', 'url': '/', 'new_window': True},
        {'model': 'auth.User'},
        {'app': 'media'},
    ],
    
    #############
    # User Menu #
    #############
    'usermenu_links': [
        {'model': 'auth.user'},
    ],
    
    #############
    # Side Menu #
    #############
    'show_sidebar': True,
    
    'navigation_expanded': True,
    
    'hide_apps': [],
    
    'hide_models': [],
    
    'order_with_respect_to': ['auth', 'core', 'categories', 'media', 'collections', 'comments', 'inquiries'],
    
    'custom_links': {
        'media': [{
            'name': 'Upload Media',
            'url': 'admin:media_mediaitem_add',
            'icon': 'fas fa-upload',
            'permissions': ['media.add_mediaitem']
        }]
    },
    
    'icons': {
        'auth': 'fas fa-users-cog',
        'auth.user': 'fas fa-user',
        'auth.Group': 'fas fa-users',
        
        'core': 'fas fa-cog',
        'core.SiteSettings': 'fas fa-sliders-h',
        
        'categories': 'fas fa-tags',
        'categories.Category': 'fas fa-folder',
        
        'media': 'fas fa-camera',
        'media.MediaItem': 'fas fa-image',
        'media.MediaGallery': 'fas fa-layer-group',
        'media.GalleryItem': 'fas fa-th',
        
        'collections': 'fas fa-collection',
        'collections.Collection': 'fas fa-album',
        'collections.CollectionItem': 'fas fa-link',
        
        'comments': 'fas fa-comments',
        'comments.Comment': 'fas fa-comment',
        'comments.Testimonial': 'fas fa-star',
        
        'inquiries': 'fas fa-envelope',
        'inquiries.Inquiry': 'fas fa-question-circle',
    },
    
    'default_icon_parents': 'fas fa-chevron-circle-right',
    'default_icon_children': 'fas fa-circle',
    
    #################
    # Related Modal #
    #################
    'related_modal_active': True,
    
    #############
    # UI Tweaks #
    #############
    'custom_css': None,
    'custom_js': None,
    'use_google_fonts_cdn': True,
    'show_ui_builder': DEBUG,
    
    ###############
    # Change view #
    ###############
    'changeform_format': 'horizontal_tabs',
    'changeform_format_overrides': {
        'auth.user': 'collapsible',
        'auth.group': 'vertical_tabs',
        'media.MediaItem': 'horizontal_tabs',
        'inquiries.Inquiry': 'horizontal_tabs',
    },
}

# Jazzmin UI Customizer Settings
JAZZMIN_UI_TWEAKS = {
    'navbar_small_text': False,
    'footer_small_text': False,
    'body_small_text': False,
    'brand_small_text': False,
    'brand_colour': 'navbar-dark',
    'accent': 'accent-primary',
    'navbar': 'navbar-dark',
    'no_navbar_border': False,
    'navbar_fixed': True,
    'layout_boxed': False,
    'footer_fixed': False,
    'sidebar_fixed': True,
    'sidebar': 'sidebar-dark-primary',
    'sidebar_nav_small_text': False,
    'sidebar_disable_expand': False,
    'sidebar_nav_child_indent': True,
    'sidebar_nav_compact_style': False,
    'sidebar_nav_legacy_style': False,
    'sidebar_nav_flat_style': False,
    'theme': 'darkly',
    'dark_mode_theme': 'cyborg',
    'button_classes': {
        'primary': 'btn-primary',
        'secondary': 'btn-secondary',
        'info': 'btn-info',
        'warning': 'btn-warning',
        'danger': 'btn-danger',
        'success': 'btn-success',
    },
}
```

### Update requirements.txt (Add Jazzmin)
```bash
# Add to requirements.txt
echo "django-jazzmin==2.6.0" >> requirements.txt
```

### Optional: Create Jazzmin Custom CSS
```bash
mkdir -p static/css
touch static/css/jazzmin-custom.css
```

```css
/* static/css/jazzmin-custom.css */
:root {
    --jazzmin-primary: #149ddd;
    --jazzmin-secondary: #37b3ed;
    --jazzmin-success: #28a745;
    --jazzmin-info: #17a2b8;
    --jazzmin-warning: #ffc107;
    --jazzmin-danger: #dc3545;
    --jazzmin-dark: #343a40;
}

/* Custom card styling */
.card {
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s;
}

.card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
}

/* Custom button styling */
.btn {
    border-radius: 5px;
    font-weight: 500;
    padding: 8px 16px;
    transition: all 0.2s;
}

.btn-primary {
    background: linear-gradient(135deg, var(--jazzmin-primary), var(--jazzmin-secondary));
    border: none;
}

.btn-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(20, 157, 221, 0.3);
}

/* Custom table styling */
.table thead th {
    background: linear-gradient(135deg, var(--jazzmin-primary), var(--jazzmin-secondary));
    color: white;
    border: none;
    font-weight: 500;
}

.table tbody tr:hover {
    background: rgba(20, 157, 221, 0.05);
}

/* Custom image preview in admin */
.field-media_preview img {
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s;
}

.field-media_preview img:hover {
    transform: scale(1.1);
}

/* Custom status badges */
.badge-success {
    background: linear-gradient(135deg, #28a745, #20c997);
    color: white;
    padding: 5px 10px;
    border-radius: 20px;
}

.badge-warning {
    background: linear-gradient(135deg, #ffc107, #fd7e14);
    color: white;
    padding: 5px 10px;
    border-radius: 20px;
}

.badge-danger {
    background: linear-gradient(135deg, #dc3545, #c82333);
    color: white;
    padding: 5px 10px;
    border-radius: 20px;
}

/* Custom dashboard cards */
.dashboard-card {
    background: linear-gradient(135deg, var(--jazzmin-primary), var(--jazzmin-secondary));
    color: white;
    border-radius: 15px;
    padding: 20px;
    margin-bottom: 20px;
}

.dashboard-card h3 {
    color: white;
    font-size: 32px;
    font-weight: 700;
    margin: 0;
}

.dashboard-card p {
    color: rgba(255, 255, 255, 0.9);
    margin: 5px 0 0;
    font-size: 14px;
}

/* Custom login form */
.login-box {
    background: white;
    border-radius: 15px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
    padding: 40px;
}

.login-logo {
    margin-bottom: 30px;
}

.login-logo b {
    background: linear-gradient(135deg, var(--jazzmin-primary), var(--jazzmin-secondary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 28px;
}

/* Custom filter sidebar */
.filter-sidebar {
    background: linear-gradient(135deg, #f8f9fa, #e9ecef);
    border-radius: 10px;
    padding: 20px;
}

/* Custom action buttons */
.actions-wrapper {
    background: linear-gradient(135deg, #f8f9fa, #e9ecef);
    border-radius: 10px;
    padding: 15px;
    margin-bottom: 20px;
}

/* Custom pagination */
.pagination .page-link {
    border-radius: 5px;
    margin: 0 2px;
    color: var(--jazzmin-primary);
}

.pagination .page-item.active .page-link {
    background: linear-gradient(135deg, var(--jazzmin-primary), var(--jazzmin-secondary));
    border: none;
}
```

### Update to use custom CSS in settings
```python
# Add this to the JAZZMIN_SETTINGS dictionary
'custom_css': 'css/jazzmin-custom.css',
```

## Key Jazzmin Features Added:

### 🎨 **Visual Enhancements**
- Modern, clean admin interface with gradient accents
- Dark theme support with 'darkly' and 'cyborg' themes
- Custom icons for all models using Font Awesome
- Responsive horizontal tabs for complex models

### 📊 **Dashboard Improvements**
- Customizable top menu with quick links
- Organized side menu with proper ordering
- Quick upload button for media items
- Collapsible sections for better organization

### 🖼️ **Media Management**
- Beautiful image previews in admin
- Video thumbnails support
- Organized media gallery interface

### 📝 **Model-Specific Enhancements**
- `MediaItem`: Horizontal tabs for better organization
- `Inquiry`: Status badges and organized fields
- `Category`: Hierarchical display with icons
- `Comment`: Moderation tools with visual status

### 🎯 **UI Tweaks**
- Fixed navbar for easy navigation
- Fixed sidebar for quick access
- Child indentation in sidebar
- Custom button classes with gradients
- Related modal for inline editing

### 🌙 **Dark Mode Support**
- Built-in dark theme ('cyborg')
- Automatic switching based on user preference
- Consistent dark mode styling across all admin pages

## Installation Commands

```bash
# Install Jazzmin
pip install django-jazzmin

# Add to requirements.txt
pip freeze | grep jazzmin >> requirements.txt

# Collect static files to include Jazzmin assets
python manage.py collectstatic

# Run migrations (if any)
python manage.py migrate
```

Your admin interface will now have a stunning, modern appearance with all the Jazzmin enhancements while keeping all your existing functionality intact!




# Run Django check
python manage.py check