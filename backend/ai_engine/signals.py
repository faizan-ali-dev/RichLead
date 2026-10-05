"""Score leads against the ICP automatically on create and on enrichment.

A signal keeps scoring DRY: every creation path -- Apollo, Hunter, manual API,
future importers -- gets a score without each call site remembering to ask for
one. The recursion guard below is load-bearing: apply_icp_score writes
`icp_score` back via save(), and without the guard that write would re-trigger
this handler forever.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='leads.Lead', dispatch_uid='ai_engine.score_lead')
def score_lead_on_save(sender, instance, created, update_fields=None, **kwargs):
    # The score write itself updates only `icp_score`; ignore it to avoid
    # recursing. Any other field change (enrichment, title correction) rescopes.
    if update_fields is not None and set(update_fields) <= {'icp_score'}:
        return

    # Only score pending leads: re-ranking an already-contacted lead changes
    # nothing about what gets worked next.
    if instance.status != 'pending':
        return

    from .scoring import apply_icp_score
    from .services import get_business_profile

    try:
        profile = get_business_profile(instance.user)
        # Auto-scoring only activates once an ICP is actually defined. Without
        # criteria there is nothing to score against, so we leave the lead's
        # score untouched rather than overwriting a client-supplied or
        # enrichment-provided value with the neutral baseline.
        if profile is None or not profile.has_icp_criteria():
            return
        apply_icp_score(instance, profile)
    except Exception:
        # Scoring must never block lead creation or enrichment; a bad score is
        # recoverable, a failed import is not.
        logger.exception('ICP scoring failed for lead %s', instance.pk)
