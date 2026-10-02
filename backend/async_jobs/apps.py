from django.apps import AppConfig


class AsyncJobsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'async_jobs'
    verbose_name = 'Background jobs'
