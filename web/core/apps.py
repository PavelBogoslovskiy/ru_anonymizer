from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'web.core'

    def ready(self):
        # Импортируем сигналы при старте приложения
        try:
            import web.core.signals
        except Exception:
            pass