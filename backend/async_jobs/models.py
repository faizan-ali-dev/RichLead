import uuid

from django.conf import settings
from django.db import models


class BackgroundJob(models.Model):
    """Tenant-owned status and result record; Celery is only the transport."""

    TYPE_CHOICES = (
        ('send_email', 'Send email'),
        ('send_email_batch', 'Send email batch'),
        ('inbox_sync', 'Mailbox sync'),
        ('apollo_search', 'Apollo search'),
        ('hunter_search', 'Hunter search'),
        ('generate_draft', 'Generate draft'),
        ('draft_queue', 'Draft review queue'),
        ('followup_batch', 'Scheduled follow-ups'),
    )
    STATUS_CHOICES = (
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='background_jobs')
    job_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='queued', db_index=True)
    idempotency_key = models.CharField(max_length=128)
    request_fingerprint = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default='')
    progress_current = models.PositiveIntegerField(default=0)
    progress_total = models.PositiveIntegerField(default=0)
    progress_message = models.CharField(max_length=200, blank=True, default='')
    dispatch_attempts = models.PositiveSmallIntegerField(default=0)
    last_dispatched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'idempotency_key'], name='uniq_job_user_idempotency'),
            models.UniqueConstraint(
                fields=['user', 'job_type'],
                condition=models.Q(job_type__in=('inbox_sync', 'followup_batch'), status__in=('queued', 'running')),
                name='uniq_active_periodic_job_per_user',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'created_at'], name='async_job_status_created_idx'),
        ]

    def __str__(self):
        return f'{self.job_type} ({self.status}) for user {self.user_id}'
