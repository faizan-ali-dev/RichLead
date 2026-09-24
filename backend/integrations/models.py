from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet

import os
# For MVP, we will use a hardcoded key if one is not in settings, but in prod it MUST be in settings.
# Use a static base64 key so it survives server reloads
_static_key = getattr(settings, 'FERNET_KEY', b'K8Q7bLq9P8eB_fW1R2M3sO4T5zY6aX7cV8N9M0L1K2J=')
try:
    _CIPHER = Fernet(_static_key)
except:
    _CIPHER = Fernet(Fernet.generate_key())

def encrypt_key(api_key):
    if not api_key: return api_key
    return _CIPHER.encrypt(api_key.encode()).decode()

def decrypt_key(encrypted_key):
    if not encrypted_key: return encrypted_key
    try:
        return _CIPHER.decrypt(encrypted_key.encode()).decode()
    except:
        return encrypted_key

class APIIntegration(models.Model):
    PROVIDER_CHOICES = (
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('groq', 'Groq'),
        ('apollo', 'Apollo'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_integrations')
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    encrypted_api_key = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'provider') # A user can only have one key per provider

    def set_api_key(self, raw_key):
        self.encrypted_api_key = encrypt_key(raw_key)

    def get_api_key(self):
        return decrypt_key(self.encrypted_api_key)

    def __str__(self):
        return f"{self.provider} for {self.user.username}"


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
