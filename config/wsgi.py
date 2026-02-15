"""
WSGI config for media portfolio project.
This is the entry point for production servers like Gunicorn.
"""

import os
from django.core.wsgi import get_wsgi_application

# Use production settings on Leapcell
# The DJANGO_SETTINGS_MODULE will be set via environment variable
# Default to production settings for safety
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')

application = get_wsgi_application()