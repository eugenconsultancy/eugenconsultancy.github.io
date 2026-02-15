import os
from celery import Celery

# Set the default Django settings module - use production on Leapcell
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')

# Create Celery app
app = Celery('media_portfolio')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related config keys should have a `CELERY_` prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """
    Debug task to verify Celery is working
    """
    print(f'Request: {self.request!r}')
    return f"Task executed at {self.request.hostname}"