from django.db import models
from django.conf import settings
from leads.models import Lead
from integrations.models import EmailAccount

class EmailMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inbox_messages')
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='emails', null=True, blank=True)
    account = models.ForeignKey(EmailAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='emails')
    
    message_id = models.CharField(max_length=255, unique=True, db_index=True)
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

    def __str__(self):
        return f"{self.subject} ({self.direction})"
