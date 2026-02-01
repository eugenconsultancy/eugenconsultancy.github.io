from django.apps import AppConfig


class AIToolsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ai_tools'
    verbose_name = 'AI Writing Assistants'
    
    def ready(self):
        import apps.ai_tools.signals  # noqa