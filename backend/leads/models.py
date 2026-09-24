from django.db import models
from django.conf import settings

class Lead(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leads')
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('reached', 'Reached Out'),
        ('replied', 'Replied'),
        ('blacklisted', 'Blacklisted'),
    )

    name = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    niche = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    icp_score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.company})"

class ScoreBreakdown(models.Model):
    lead = models.ForeignKey(Lead, related_name='score_breakdowns', on_delete=models.CASCADE)
    factor = models.CharField(max_length=100)
    score = models.IntegerField()
    max_score = models.IntegerField()

    def __str__(self):
        return f"{self.factor} for {self.lead.name}"

class IntentSignal(models.Model):
    lead = models.ForeignKey(Lead, related_name='intent_signals', on_delete=models.CASCADE)
    signal = models.CharField(max_length=255)
    detected_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.signal

class AIResearch(models.Model):
    lead = models.OneToOneField(Lead, related_name='research', on_delete=models.CASCADE)
    summary = models.TextField()
    generated_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Research for {self.lead.name}"
