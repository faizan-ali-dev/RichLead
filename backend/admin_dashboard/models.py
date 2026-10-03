from django.db import models


class AnalyticsEvent(models.Model):
    EVENT_TYPES = (
        ('page_view', 'Page view'),
        ('cta_click', 'Call to action click'),
    )

    event_type = models.CharField(max_length=16, choices=EVENT_TYPES, db_index=True)
    path = models.CharField(max_length=120, db_index=True)
    label = models.CharField(max_length=64, blank=True, default='')
    session_id = models.UUIDField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at'], name='analytics_type_created_idx'),
            models.Index(fields=['path', 'created_at'], name='analytics_path_created_idx'),
        ]

    def __str__(self):
        return f'{self.event_type} {self.path}'
