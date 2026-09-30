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
    title = models.CharField(max_length=255, blank=True, default='')
    niche = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=64, blank=True, default='')
    website = models.CharField(max_length=500, blank=True, default='')
    linkedin_url = models.CharField(max_length=500, blank=True, default='')
    industry = models.CharField(max_length=150, blank=True, default='')
    location = models.CharField(max_length=255, blank=True, default='')
    employee_count = models.PositiveIntegerField(null=True, blank=True)
    funding_amount = models.CharField(max_length=100, blank=True, default='')
    funding_round = models.CharField(max_length=100, blank=True, default='')
    funding_data = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=50, blank=True, default='')
    source_id = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    icp_score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    # Event timestamps. `status` is a single mutable field, so it cannot express
    # "was sent AND replied" -- deriving metrics from it makes the denominator
    # exclude the very successes being measured.
    first_sent_at = models.DateTimeField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'email'], name='uniq_lead_email_per_user'),
        ]
        indexes = [
            models.Index(fields=['user', 'status']),
        ]

    def save(self, *args, **kwargs):
        # Reply matching lowercases inbound addresses, so storage must be normalised
        # or replies from 'Carol@Globex.test' never match a lead stored as 'carol@globex.test'.
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

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

    # The subject is written by the model alongside the body so the two match.
    # A subject that doesn't relate to the body is itself a spam signal.
    generated_subject = models.CharField(max_length=255, blank=True, default='')

    # The specific problem the model inferred for this lead. Shown in the review
    # queue so a human can judge whether the angle is right before sending.
    pain_point = models.TextField(blank=True, default='')

    # Output of prompt_rules.lint_email at generation time.
    spam_score = models.IntegerField(null=True, blank=True)
    spam_issues = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Research for {self.lead.name}"
