from django.db import models
from django.conf import settings
from leads.models import Lead
from cryptography.fernet import Fernet
from functools import lru_cache


@lru_cache(maxsize=1)
def _cipher():
    """Fernet instance built from settings.FERNET_KEY.

    Resolved lazily so an import never silently falls back to a throwaway key.
    settings.py is responsible for requiring the value from the environment.
    """
    return Fernet(settings.FERNET_KEY)


def encrypt_key(api_key):
    if not api_key:
        return api_key
    return _cipher().encrypt(api_key.encode()).decode()


def decrypt_key(encrypted_key):
    """Decrypt a stored credential.

    Deliberately propagates InvalidToken. Returning the ciphertext on failure (as the
    previous implementation did) turns a key-rotation bug into garbage being sent as
    an SMTP password, with no error anywhere.
    """
    if not encrypted_key:
        return encrypted_key
    return _cipher().decrypt(encrypted_key.encode()).decode()

class APIIntegration(models.Model):
    PROVIDER_CHOICES = (
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('groq', 'Groq'),
        ('apollo', 'Apollo'),
        ('hunter', 'Hunter'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_integrations')
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    encrypted_api_key = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # The specific model to generate with, e.g. 'claude-opus-5'. Blank for
    # non-LLM providers like Apollo.
    model = models.CharField(max_length=100, blank=True, default='')

    # Exactly one LLM integration per user is primary: the one every AI feature
    # uses. Enforced by a partial unique constraint below.
    is_primary = models.BooleanField(default=False)

    # Set when a real generation round-trip last succeeded for this key+model.
    last_validated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # A user can only have one key per provider.
            models.UniqueConstraint(fields=['user', 'provider'], name='uniq_integration_per_provider'),
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_primary=True),
                name='uniq_primary_llm_per_user',
            ),
        ]

    def set_api_key(self, raw_key):
        self.encrypted_api_key = encrypt_key(raw_key)

    def get_api_key(self):
        return decrypt_key(self.encrypted_api_key)

    def make_primary(self):
        """Promote this integration, demoting whichever one currently holds it."""
        APIIntegration.objects.filter(user=self.user, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        if not self.is_primary:
            self.is_primary = True
            self.save(update_fields=['is_primary'])

    def __str__(self):
        return f"{self.provider} for {self.user.username}"


class FollowUpSequence(models.Model):
    """Durable, indexed queue state for one lead's scheduled follow-ups."""

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('stopped', 'Stopped'),
        ('failed', 'Failed'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followup_sequences')
    lead = models.OneToOneField(Lead, on_delete=models.CASCADE, related_name='followup_sequence')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='active')
    sent_follow_ups = models.PositiveSmallIntegerField(default=0)
    next_send_at = models.DateTimeField(db_index=True)
    last_sent_at = models.DateTimeField()

    # A short lease + per-dispatch token prevents two workers from sending the
    # same due step. Expired leases are reclaimed by the next beat pass.
    claim_token = models.UUIDField(null=True, blank=True)
    claim_expires_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True, default='')
    prepared_subject = models.CharField(max_length=255, blank=True, default='')
    prepared_body = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['status', 'next_send_at'], name='followup_due_idx')]

    def __str__(self):
        return f'Follow-up sequence for lead {self.lead_id} ({self.status})'


class OAuthState(models.Model):
    """Single-use, expiring CSRF state for an in-flight OAuth authorisation."""
    state = models.CharField(max_length=128, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='oauth_states')
    provider = models.CharField(max_length=32)
    code_verifier = models.CharField(max_length=128)
    browser_binding_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.provider} state for user {self.user_id}"


class SuppressionEntry(models.Model):
    """Addresses and domains this tenant must never contact again.

    Checked on every send. Entries are permanent by design: an opt-out that can be
    undone by a status change is not an opt-out.
    """
    REASON_CHOICES = (
        ('unsubscribed', 'Unsubscribed'),
        ('bounced', 'Hard Bounced'),
        ('complained', 'Spam Complaint'),
        ('manual', 'Manually Added'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='suppressions')
    email = models.EmailField(blank=True, default='')
    domain = models.CharField(max_length=255, blank=True, default='')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default='manual')
    note = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'email'],
                condition=~models.Q(email=''),
                name='uniq_suppression_email_per_user',
            ),
            models.UniqueConstraint(
                fields=['user', 'domain'],
                condition=~models.Q(domain=''),
                name='uniq_suppression_domain_per_user',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'email']),
            models.Index(fields=['user', 'domain']),
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or '').strip().lower()
        self.domain = (self.domain or '').strip().lower().lstrip('@').rstrip('.')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email or f"@{self.domain}"


def is_suppressed(user, email):
    """True if this tenant is barred from emailing `email`, by address or by domain."""
    if not email:
        return False
    email = email.strip().lower()
    domain = email.split('@')[-1]
    return SuppressionEntry.objects.filter(user=user).filter(
        models.Q(email=email) | models.Q(domain=domain)
    ).exists()


class EmailAccount(models.Model):
    AUTH_TYPE_CHOICES = (
        ('smtp', 'Custom SMTP'),
        ('oauth_google', 'Google OAuth'),
        ('oauth_microsoft', 'Microsoft OAuth'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_accounts')
    email_address = models.EmailField()
    provider = models.CharField(max_length=50, default='smtp')
    auth_type = models.CharField(max_length=20, choices=AUTH_TYPE_CHOICES, default='smtp')
    
    # SMTP details (used if auth_type == 'smtp')
    smtp_host = models.CharField(max_length=255, blank=True, null=True)
    smtp_port = models.IntegerField(default=587, blank=True, null=True)
    encrypted_password = models.CharField(max_length=500, blank=True, null=True)

    # IMAP details (used if auth_type == 'smtp' for reading emails)
    imap_host = models.CharField(max_length=255, blank=True, null=True)
    imap_port = models.IntegerField(default=993, blank=True, null=True)
    encrypted_imap_password = models.CharField(max_length=500, blank=True, null=True)
    
    # OAuth details (used if auth_type.startswith('oauth'))
    encrypted_access_token = models.CharField(max_length=2000, blank=True, null=True)
    encrypted_refresh_token = models.CharField(max_length=2000, blank=True, null=True)
    token_expiry = models.DateTimeField(blank=True, null=True)
    
    is_connected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Provider limits are hard (Gmail ~500/day, Outlook ~300/day) and cold-outreach
    # patterns trip them fast. Exceeding them gets the mailbox suspended.
    daily_send_limit = models.PositiveIntegerField(default=50)
    sends_today = models.PositiveIntegerField(default=0)
    sends_counted_on = models.DateField(null=True, blank=True)

    def remaining_sends_today(self):
        from django.utils import timezone

        if self.sends_counted_on != timezone.now().date():
            return self.daily_send_limit
        return max(0, self.daily_send_limit - self.sends_today)

    def record_send(self):
        from django.utils import timezone

        today = timezone.now().date()
        if self.sends_counted_on != today:
            self.sends_counted_on = today
            self.sends_today = 0
        self.sends_today += 1
        self.save(update_fields=['sends_today', 'sends_counted_on'])

    def set_password(self, raw_password):
        self.encrypted_password = encrypt_key(raw_password)

    def get_password(self):
        return decrypt_key(self.encrypted_password)

    def set_imap_password(self, raw_password):
        self.encrypted_imap_password = encrypt_key(raw_password)

    def get_imap_password(self):
        return decrypt_key(self.encrypted_imap_password)
        
    def set_oauth_tokens(self, access_token, refresh_token=None):
        if access_token:
            self.encrypted_access_token = encrypt_key(access_token)
        if refresh_token:
            self.encrypted_refresh_token = encrypt_key(refresh_token)
            
    def get_access_token(self):
        return decrypt_key(self.encrypted_access_token)
        
    def get_refresh_token(self):
        return decrypt_key(self.encrypted_refresh_token)

    def __str__(self):
        return self.email_address
