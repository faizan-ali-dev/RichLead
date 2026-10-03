from django.apps import AppConfig


class AdminDashboardConfig(AppConfig):
    name = 'admin_dashboard'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from django.contrib import admin

        from . import signals  # noqa: F401

        admin.site.site_header = 'RichLead Control Center'
        admin.site.site_title = 'RichLead Admin'
        admin.site.index_title = 'Platform overview'
        admin.site.index_template = 'admin_dashboard/index.html'
