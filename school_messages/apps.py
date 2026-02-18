from django.apps import AppConfig

class SchoolMessagesConfig(AppConfig):  # Changed class name
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'school_messages'  # Changed name