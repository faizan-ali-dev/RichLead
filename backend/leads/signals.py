"""Invalidate dashboard summaries after committed source-data changes."""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from inbox.models import EmailMessage
from integrations.models import SuppressionEntry
from richlead_backend.caching import invalidate_dashboard_stats

from .models import AIResearch, Lead


def _schedule_invalidation(user_id):
    if user_id:
        transaction.on_commit(lambda: invalidate_dashboard_stats(user_id))


@receiver([post_save, post_delete], sender=Lead)
def invalidate_after_lead_change(sender, instance, **kwargs):
    _schedule_invalidation(instance.user_id)


@receiver([post_save, post_delete], sender=EmailMessage)
def invalidate_after_email_change(sender, instance, **kwargs):
    _schedule_invalidation(instance.user_id)


@receiver([post_save, post_delete], sender=SuppressionEntry)
def invalidate_after_suppression_change(sender, instance, **kwargs):
    _schedule_invalidation(instance.user_id)


@receiver([post_save, post_delete], sender=AIResearch)
def invalidate_after_research_change(sender, instance, **kwargs):
    user_id = Lead.objects.filter(pk=instance.lead_id).values_list('user_id', flat=True).first()
    _schedule_invalidation(user_id)
