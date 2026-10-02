import logging
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from async_jobs.services import JobQueueUnavailable, enqueue_job
from integrations.models import EmailAccount

logger = logging.getLogger(__name__)


@shared_task(name='inbox.enqueue_periodic_syncs')
def enqueue_periodic_syncs():
    """Queue a low-frequency server-side sync for each active connected mailbox owner."""
    user_model = get_user_model()
    now = timezone.now()
    slot = now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0)
    user_ids = EmailAccount.objects.filter(
        user__is_active=True, is_connected=True,
    ).values_list('user_id', flat=True).distinct()
    queued = 0
    for user_id in user_ids.iterator():
        user = user_model.objects.filter(pk=user_id, is_active=True).first()
        if user is None:
            continue
        try:
            enqueue_job(
                user,
                'inbox_sync',
                {},
                idempotency_key=f'periodic-mailbox-sync:{user_id}:{slot:%Y%m%d%H%M}',
            )
            queued += 1
        except JobQueueUnavailable:
            logger.warning('Could not queue periodic mailbox sync for user %s', user_id)
    return {'queued': queued}
