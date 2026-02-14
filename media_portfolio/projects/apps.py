from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'media_portfolio.projects'
    verbose_name = 'Projects Portfolio'

    def ready(self):
        import media_portfolio.projects.signals