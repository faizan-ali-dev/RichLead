from django.apps import AppConfig


class LeadsConfig(AppConfig):
    name = 'leads'

    def ready(self):
        from . import signals  # noqa: F401
