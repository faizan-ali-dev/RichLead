"""A/B testing of subject-line approaches.

Testing bespoke per-lead subjects against each other is not a valid experiment --
every subject is different, so there is nothing to compare. What *is* testable is
the subject-writing *approach*: "lead with a question" vs "lead with the pain
point". Each pending lead is randomly assigned one approach, the subject is
generated under that instruction, and reply rate is compared across approaches.
Once one approach wins with enough volume, it is promoted and all new leads use
it.

The experiment config and model live here; the per-lead variant is a field on
Lead so no join is needed to aggregate results.
"""
import math

from django.conf import settings
from django.db import models


class SubjectExperiment(models.Model):
    """One A/B test of two subject-writing approaches for a tenant."""

    STATUS_CHOICES = (
        ('off', 'Off'),
        ('running', 'Running'),
        ('decided', 'Decided'),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subject_experiment',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='off')

    variant_a_label = models.CharField(max_length=80, default='Question style')
    variant_a_instruction = models.TextField(
        default='Write the subject as a short, specific question about their work.',
    )
    variant_b_label = models.CharField(max_length=80, default='Pain-point style')
    variant_b_instruction = models.TextField(
        default='Write the subject as a plain statement naming the problem you solve for them.',
    )

    winner = models.CharField(max_length=1, blank=True, default='')  # 'a' | 'b' | ''
    decided_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Guardrails so a winner is never called on noise.
    MIN_SENT_PER_VARIANT = 30
    MIN_REPLY_RATE_GAP = 0.03  # 3 percentage points

    def instruction_for(self, variant):
        return self.variant_a_instruction if variant == 'a' else self.variant_b_instruction

    def __str__(self):
        return f'Subject experiment for {self.user_id} ({self.status})'


def _two_proportion_z(x1, n1, x2, n2):
    """Z statistic for the difference between two reply rates. 0 when undefined."""
    if n1 == 0 or n2 == 0:
        return 0.0
    p1, p2 = x1 / n1, x2 / n2
    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0
    return (p1 - p2) / se


def experiment_results(user):
    """Per-variant sent/replied counts and reply rates for the live experiment."""
    from leads.models import Lead

    rows = (
        Lead.objects.filter(user=user, subject_variant__in=('a', 'b'), first_sent_at__isnull=False)
        .values('subject_variant')
        .annotate(
            sent=models.Count('id'),
            replied=models.Count('id', filter=models.Q(replied_at__isnull=False)),
        )
    )
    stats = {'a': {'sent': 0, 'replied': 0}, 'b': {'sent': 0, 'replied': 0}}
    for row in rows:
        stats[row['subject_variant']] = {'sent': row['sent'], 'replied': row['replied']}

    for v in ('a', 'b'):
        sent = stats[v]['sent']
        stats[v]['reply_rate'] = round(stats[v]['replied'] / sent, 4) if sent else 0.0

    return stats


def evaluate_experiment(user, experiment=None):
    """Decide a winner when the data supports it. Returns the (possibly new) winner.

    Conservative on purpose: requires a minimum sample per variant, a minimum
    reply-rate gap, and z > 1.96 (~95% confidence) before promoting. Until then
    the experiment keeps running and assignment stays 50/50.
    """
    from django.utils import timezone

    experiment = experiment or SubjectExperiment.objects.filter(user=user).first()
    if experiment is None or experiment.status != 'running':
        return experiment.winner if experiment else ''

    stats = experiment_results(user)
    a, b = stats['a'], stats['b']
    if a['sent'] < SubjectExperiment.MIN_SENT_PER_VARIANT or b['sent'] < SubjectExperiment.MIN_SENT_PER_VARIANT:
        return ''

    gap = abs(a['reply_rate'] - b['reply_rate'])
    z = abs(_two_proportion_z(a['replied'], a['sent'], b['replied'], b['sent']))
    if gap < SubjectExperiment.MIN_REPLY_RATE_GAP or z < 1.96:
        return ''

    winner = 'a' if a['reply_rate'] >= b['reply_rate'] else 'b'
    experiment.winner = winner
    experiment.status = 'decided'
    experiment.decided_at = timezone.now()
    experiment.save(update_fields=['winner', 'status', 'decided_at', 'updated_at'])
    return winner


def assign_variant(user, lead, experiment=None):
    """Pick and persist the subject variant this lead should be drafted under.

    Returns (variant, instruction) or (None, '') when no experiment applies.
    After a winner is decided, every new lead gets the winning approach. While
    running, assignment is random 50/50 and sticky per lead.
    """
    import random

    experiment = experiment or SubjectExperiment.objects.filter(user=user).first()
    if experiment is None or experiment.status == 'off':
        return None, ''

    if experiment.status == 'decided':
        variant = experiment.winner or 'a'
    elif lead.subject_variant in ('a', 'b'):
        variant = lead.subject_variant  # sticky: don't re-roll on regenerate
    else:
        variant = random.choice(('a', 'b'))

    if lead.subject_variant != variant:
        lead.subject_variant = variant
        lead.save(update_fields=['subject_variant'])

    return variant, experiment.instruction_for(variant)
