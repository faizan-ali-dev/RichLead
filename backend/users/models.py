from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    REACHOUT_LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('ur', 'Urdu (اردو)'),
        ('ar', 'Arabic (العربية)'),
        ('hi', 'Hindi (हिन्दी)'),
        ('es', 'Spanish (Español)'),
        ('fr', 'French (Français)'),
        ('de', 'German (Deutsch)'),
        ('pt', 'Portuguese (Português)'),
        ('it', 'Italian (Italiano)'),
        ('nl', 'Dutch (Nederlands)'),
        ('tr', 'Turkish (Türkçe)'),
        ('ja', 'Japanese (日本語)'),
        ('zh', 'Chinese, Simplified (简体中文)'),
    )

    autopilot_active = models.BooleanField(default=False, help_text="If true, AI emails are sent automatically without manual review.")
    reachout_language = models.CharField(max_length=5, choices=REACHOUT_LANGUAGE_CHOICES, default='en')
    email_verified = models.BooleanField(default=False)
    email_verification_code_hash = models.CharField(max_length=128, blank=True)
    email_verification_expires_at = models.DateTimeField(null=True, blank=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    email_verification_attempts = models.PositiveSmallIntegerField(default=0)

    # How recipients are given a way to opt out. This is a real trade-off, not a
    # preference: the List-Unsubscribe header is a bulk-mail marker and one of
    # Gmail's strongest Promotions-tab signals, but it is required of senders
    # above ~5,000 messages/day. Low-volume 1:1 outreach is compliant with a
    # plain-text opt-out line and lands in Primary far more often.
    UNSUBSCRIBE_MODE_CHOICES = (
        ('text', 'Plain-text line in the body (best for Primary tab)'),
        ('header', 'List-Unsubscribe header only (required for bulk senders)'),
        ('both', 'Both'),
    )
    unsubscribe_mode = models.CharField(max_length=10, choices=UNSUBSCRIBE_MODE_CHOICES, default='text')

    # Appended when unsubscribe_mode includes 'text'. Phrased as a human would.
    unsubscribe_text = models.CharField(
        max_length=200,
        default="If you'd rather not hear from me, just reply with 'no thanks' and I'll leave you alone.",
    )
