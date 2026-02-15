# Web process - handles HTTP requests
web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --threads 2 --timeout 120 --access-logfile - --error-logfile -

# Release phase - runs once before new version is deployed
release: python manage.py migrate --noinput

# Celery worker - handles background tasks (optional)
worker: celery -A config worker --loglevel=info --concurrency=2 -E

# Celery beat - scheduled tasks (optional)
beat: celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler