from django.db import models
from django.conf import settings
from leads.models import Lead
from integrations.models import EmailAccount

class EmailMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inbox_messages')
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='emails', null=True, blank=True)
    account = models.ForeignKey(EmailAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='emails')
    
    # The provider's own identifier (Gmail/Graph internal id, or an IMAP UID).
    message_id = models.CharField(max_length=255, db_index=True)

    # The RFC 5322 Message-ID, which is stable across mailboxes and survives the
    # round trip. Recorded when we send so the later mailbox sync can recognise
    # its own outbound mail instead of storing a second copy of it.
    rfc_message_id = models.CharField(max_length=500, blank=True, default='', db_index=True)
    subject = models.CharField(max_length=500, blank=True, null=True)
    from_email = models.CharField(max_length=255)
    to_email = models.CharField(max_length=255)
    body_text = models.TextField(blank=True, null=True)
    body_html = models.TextField(blank=True, null=True)
    
    received_at = models.DateTimeField()
    is_read = models.BooleanField(default=False)
    
    # 'inbound' means Lead -> User. 'outbound' means User -> Lead.
    DIRECTION_CHOICES = (
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='inbound')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']
        constraints = [
            # Both parties on a shared thread must each keep their own copy.
            models.UniqueConstraint(fields=['user', 'message_id'], name='uniq_message_per_user'),
        ]
        indexes = [
            models.Index(fields=['user', '-received_at']),
        ]

    def __str__(self):
        return f"{self.subject} ({self.direction})"
