"""Business profile and follow-up cadence.

The business profile is the single biggest lever on draft quality. Without it the
model has to invent what the sender sells, which is what makes cold email read as
generic. It is deliberately separate from PromptTemplate: the prompt controls
*how* to write, this controls *what is true about the business*.
"""
from django.conf import settings
from django.db import models


class BusinessProfile(models.Model):
    """What the tenant sells, who they sell it to, and why anyone should care."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='business_profile',
    )

    company_name = models.CharField(max_length=200, blank=True, default='')
    website = models.CharField(max_length=300, blank=True, default='')
    industry = models.CharField(max_length=150, blank=True, default='')

    # The pitch, in the sender's own words.
    what_you_do = models.TextField(
        blank=True, default='',
        help_text="Plain description of the product or service, as you would say it out loud.",
    )
    problem_you_solve = models.TextField(
        blank=True, default='',
        help_text="The problem customers hire you to fix. The email opens on the prospect's version of this.",
    )
    ideal_customer = models.TextField(
        blank=True, default='',
        help_text="Who this is for: company size, role, industry.",
    )
    differentiator = models.TextField(
        blank=True, default='',
        help_text="Why you rather than the obvious alternative.",
    )
    proof_points = models.TextField(
        blank=True, default='',
        help_text="Concrete, checkable results. One per line.",
    )
    case_study = models.TextField(
        blank=True, default='',
        help_text="A named customer story the model may reference when it fits.",
    )

    # Guardrails on what the model may claim.
    never_claim = models.TextField(
        blank=True, default='',
        help_text="Claims the model must never make, e.g. compliance certifications you do not hold.",
    )

    sender_name = models.CharField(max_length=150, blank=True, default='')
    sender_title = models.CharField(max_length=150, blank=True, default='')

    updated_at = models.DateTimeField(auto_now=True)

    def is_complete(self):
        """True once there is enough here for the model to pitch without inventing."""
        return bool(self.what_you_do.strip() and self.problem_you_solve.strip())

    def as_prompt_block(self):
        """Render as a labelled context block, or '' when nothing is filled in.

        Returned as plain labelled lines rather than JSON so it reads naturally to
        the model and stays stable byte-for-byte between requests (prompt caching).
        """
        rows = [
            ('Company', self.company_name),
            ('Industry', self.industry),
            ('What we do', self.what_you_do),
            ('Problem we solve', self.problem_you_solve),
            ('Who we serve', self.ideal_customer),
            ('Why us over alternatives', self.differentiator),
            ('Proof points', self.proof_points),
            ('Customer story', self.case_study),
            ('Sender', ' '.join(p for p in (self.sender_name, self.sender_title) if p)),
        ]
        lines = [f'{label}: {value.strip()}' for label, value in rows if value and value.strip()]

        if not lines:
            return ''

        block = 'ABOUT THE BUSINESS YOU ARE WRITING FOR:\n' + '\n'.join(lines)

        if self.never_claim.strip():
            block += (
                f'\n\nNEVER CLAIM ANY OF THE FOLLOWING, even if it would strengthen the pitch:\n'
                f'{self.never_claim.strip()}'
            )

        block += (
            '\n\nPitch only what is stated above. Do not invent features, customers, '
            'metrics or integrations that are not listed.'
        )
        return block

    def __str__(self):
        return self.company_name or f'Business profile for {self.user.username}'


class FollowUpSettings(models.Model):
    """How many follow-ups to send and how far apart.

    Replaces the old multi-step sequence builder: for 1:1 cold outreach the only
    decisions that matter are how many times to follow up and how long to wait.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followup_settings',
    )

    enabled = models.BooleanField(default=True)

    # Beyond about four touches, reply rate falls and complaint rate climbs.
    total_follow_ups = models.PositiveIntegerField(
        default=2,
        help_text="Follow-ups after the first email. 0 means send once and stop.",
    )
    days_between = models.PositiveIntegerField(
        default=4,
        help_text="Days to wait between touches.",
    )

    # A reply is the goal, so stopping on one is not optional.
    stop_on_reply = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    MAX_FOLLOW_UPS = 5
    MIN_DAYS_BETWEEN = 2

    def clean_values(self):
        """Clamp to ranges that will not wreck sender reputation."""
        self.total_follow_ups = min(self.total_follow_ups, self.MAX_FOLLOW_UPS)
        self.days_between = max(self.days_between, self.MIN_DAYS_BETWEEN)

    def save(self, *args, **kwargs):
        self.clean_values()
        super().save(*args, **kwargs)

    def total_touches(self):
        return 1 + self.total_follow_ups

    def __str__(self):
        return f'{self.total_touches()} touches every {self.days_between}d for {self.user.username}'
