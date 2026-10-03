from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
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


class LoginActivity(models.Model):
    """A minimal sign-in audit trail for the platform control panel."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_login_activities',
    )
    logged_in_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-logged_in_at']
        indexes = [models.Index(fields=['user', 'logged_in_at'], name='admin_login_user_time_idx')]

    def __str__(self):
        return f'Sign-in at {self.logged_in_at:%Y-%m-%d %H:%M}'


class SocialLink(models.Model):
    PLATFORM_CHOICES = (
        ('linkedin', 'LinkedIn'),
        ('x', 'X'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('youtube', 'YouTube'),
        ('tiktok', 'TikTok'),
        ('threads', 'Threads'),
        ('github', 'GitHub'),
        ('reddit', 'Reddit'),
        ('discord', 'Discord'),
        ('whatsapp', 'WhatsApp'),
        ('other', 'Other'),
    )

    platform = models.CharField(max_length=16, choices=PLATFORM_CHOICES)
    label = models.CharField(max_length=48, blank=True, help_text='Optional accessible name for this account.')
    url = models.URLField(max_length=500)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'id']

    def clean(self):
        super().clean()
        if self.url and urlsplit(self.url).scheme.lower() != 'https':
            raise ValidationError({'url': 'Use a secure https:// social profile URL.'})

    @property
    def public_label(self):
        return self.label.strip() or self.get_platform_display()

    def __str__(self):
        return self.public_label
