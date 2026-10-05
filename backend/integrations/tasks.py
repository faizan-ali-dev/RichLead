import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from async_jobs.models import BackgroundJob
from async_jobs.services import JobQueueUnavailable, enqueue_job
from .models import EmailAccount, FollowUpSequence

logger = logging.getLogger(__name__)


@shared_task(name='integrations.enqueue_due_followups')
def enqueue_due_followups():
    """Queue follow-ups only after a recent successful mailbox sync checked for replies."""
    now = timezone.now()
    user_ids = FollowUpSequence.objects.filter(
        status='active', next_send_at__lte=now,
    ).values_list('user_id', flat=True).distinct()
    queued = 0
    deferred = 0
    minute_slot = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)
    user_model = get_user_model()
    for user_id in user_ids.iterator():
        user = user_model.objects.filter(pk=user_id, is_active=True).first()
        if user is None:
            continue

        if not EmailAccount.objects.filter(user_id=user_id, is_connected=True).exists():
            # Avoid spending LLM credits drafting a message that has no sender.
            deferred += 1
            continue

        fresh_sync = BackgroundJob.objects.filter(
            user_id=user_id,
            job_type='inbox_sync',
            status='succeeded',
            finished_at__gte=now - timedelta(minutes=10),
        ).exists()
        if not fresh_sync:
            # A follow-up must not go out until we have checked for a reply.
            key = f'followup-reply-sync:{user_id}:{minute_slot:%Y%m%d%H%M}'
            try:
                enqueue_job(user, 'inbox_sync', {}, idempotency_key=key)
            except JobQueueUnavailable:
                logger.warning('Could not queue reply-check mailbox sync for user %s', user_id)
            deferred += 1
            continue

        key = f'followup-batch:{user_id}:{now.strftime("%Y%m%d%H%M")}'
        try:
            enqueue_job(user, 'followup_batch', {}, idempotency_key=key)
            queued += 1
        except JobQueueUnavailable:
            logger.warning('Could not queue due follow-ups for user %s', user_id)

    return {'queued': queued, 'waiting_for_mailbox_sync': deferred}


@shared_task(name='integrations.dispatch_scheduled_sends')
def dispatch_scheduled_sends():
    """Hand every due send-time-optimized email to the ordinary send pipeline."""
    from .scheduled_sends import dispatch_due_scheduled_sends

    return dispatch_due_scheduled_sends()


@shared_task(name='integrations.monitor_deliverability')
def monitor_deliverability():
    """Re-check SPF/DKIM/DMARC for every tenant that sends mail, flagging drift.

    Runs on a slow cadence (authentication records rarely change) and only for
    users with a connected mailbox. Per-user failures are isolated so one bad
    domain cannot stall the whole sweep.
    """
    from .deliverability import run_deliverability_monitor

    user_ids = (
        EmailAccount.objects.filter(is_connected=True)
        .values_list('user_id', flat=True).distinct()
    )
    user_model = get_user_model()
    checked_users = 0
    alerts = 0
    for user_id in user_ids.iterator():
        user = user_model.objects.filter(pk=user_id, is_active=True).first()
        if user is None:
            continue
        try:
            rows = run_deliverability_monitor(user)
        except Exception:  # noqa: BLE001 - never let one tenant stop the sweep
            logger.exception('Deliverability monitor failed for user %s', user_id)
            continue
        checked_users += 1
        alerts += sum(1 for row in rows if row.has_alert)

    return {'users_checked': checked_users, 'alerts': alerts}
