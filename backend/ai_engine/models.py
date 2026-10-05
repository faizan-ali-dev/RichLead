from django.db import models
from django.conf import settings

DEFAULT_SYSTEM_PROMPT = (
    "You are an experienced SDR writing a first-touch cold email. "
    "Identify the single most likely problem this prospect has right now, then open with it. "
    "Earn a reply, not a meeting."
)


class PromptTemplate(models.Model):
    """Tenant-editable half of the generation prompt.

    The non-negotiable output rules (no em dashes, anti-spam, human voice,
    subject constraints) live in ai_engine.prompt_rules and are always appended
    after these fields. Users can shape the message; they cannot remove the
    guardrails that keep it out of spam.
    """
    TONE_CHOICES = (
        ('Direct and professional', 'Direct and professional'),
        ('Warm and conversational', 'Warm and conversational'),
        ('Blunt and to the point', 'Blunt and to the point'),
        ('Curious and consultative', 'Curious and consultative'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='prompt_templates')
    name = models.CharField(max_length=100, default="Default Outreach")
    system_prompt = models.TextField(default=DEFAULT_SYSTEM_PROMPT)
    tone_of_voice = models.CharField(max_length=50, choices=TONE_CHOICES, default='Direct and professional')

    # Context about the sender. Without these the model invents a value
    # proposition, which is the most common cause of generic-sounding output.
    sender_role = models.CharField(
        max_length=150, blank=True, default='',
        help_text="Who the email is from, e.g. 'Founder at Acme, a deliverability tool for B2B teams'.",
    )
    value_proposition = models.TextField(
        blank=True, default='',
        help_text="What you actually do for customers, in one or two plain sentences.",
    )
    proof_point = models.CharField(
        max_length=300, blank=True, default='',
        help_text="One concrete, checkable result, e.g. 'took Loop from 4% to 11% reply rate in 6 weeks'.",
    )
    call_to_action = models.CharField(
        max_length=200, blank=True,
        default='Ask if the problem is worth a short conversation. Do not ask for a meeting or send a link.',
    )
    avoid_topics = models.CharField(
        max_length=300, blank=True, default='',
        help_text="Anything the email must never mention.",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_active=True),
                name='uniq_active_prompt_per_user',
            ),
        ]

    def activate(self):
        PromptTemplate.objects.filter(user=self.user, is_active=True).exclude(pk=self.pk).update(is_active=False)
        if not self.is_active:
            self.is_active = True
            self.save(update_fields=['is_active'])

    def sender_context(self):
        """The tenant-supplied context block, or '' when nothing is configured."""
        lines = []
        if self.sender_role:
            lines.append(f"You are writing as: {self.sender_role}")
        if self.value_proposition:
            lines.append(f"What you offer: {self.value_proposition}")
        if self.proof_point:
            lines.append(f"Proof you may cite (only if it fits naturally): {self.proof_point}")
        if self.call_to_action:
            lines.append(f"Call to action: {self.call_to_action}")
        if self.avoid_topics:
            lines.append(f"Never mention: {self.avoid_topics}")
        return "\n".join(lines)

    def __str__(self):
        return f"{self.name} for {self.user.username}"


# Business profile, follow-up cadence, and the subject A/B experiment live in
# their own modules for clarity, but must be imported here so Django registers
# them with this app.
from .business import BusinessProfile, FollowUpSettings  # noqa: E402,F401
from .experiments import SubjectExperiment  # noqa: E402,F401
