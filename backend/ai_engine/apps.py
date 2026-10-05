from django.apps import AppConfig

class AIEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_engine'

    def ready(self):
        # Register model signals (ICP auto-scoring) on app load.
        from . import signals  # noqa: F401
