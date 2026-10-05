"""Create and dispatch send-time-optimized emails.

`schedule_send` computes the next in-window slot in the recipient's timezone and
stores a ScheduledSend. A beat task calls `dispatch_due_scheduled_sends`, which
hands each due row to the ordinary send_email background job -- so the real send
still flows through send_outreach_email and inherits every suppression, daily
cap, and dedupe guarantee.
"""
import logging
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import ScheduledSend, SendingWindow
from .sendtime import infer_timezone, next_send_time

logger = logging.getLogger(__name__)

CLAIM_TTL = timedelta(minutes=10)
MAX_DISPATCH_PER_RUN = 100


def get_sending_window(user):
    window, _ = SendingWindow.objects.get_or_create(user=user)
    return window


def compute_send_at(user, lead, *, now=None):
    """The optimal send instant for this lead, and the tz it was based on."""
    window = get_sending_window(user)
    tz = infer_timezone(lead.location, default=window.fallback_timezone)
    send_at = next_send_time(window, tz, now=now)
    return send_at, str(tz)


def schedule_send(user, lead, body, *, subject=None, account_id=None, now=None):
    """Replace any existing scheduled send for this lead with a new one.

    Returns the ScheduledSend. Approving a draft again simply reschedules.
    """
    send_at, tz_name = compute_send_at(user, lead, now=now)

    with transaction.atomic():
        ScheduledSend.objects.filter(user=user, lead=lead, status='scheduled').update(
            status='cancelled', updated_at=timezone.now(),
        )
        scheduled = ScheduledSend.objects.create(
            user=user,
            lead=lead,
            account_id=account_id if account_id not in (None, 'rotate') else None,
            subject=(subject or '')[:255],
            body=body,
            recipient_timezone=tz_name,
            send_at=send_at,
        )
    return scheduled


def cancel_scheduled_send(user, lead):
    return ScheduledSend.objects.filter(user=user, lead=lead, status='scheduled').update(
        status='cancelled', updated_at=timezone.now(),
    )


def _claim_due(now, user=None):
    """Atomically lease one batch of due rows so parallel beats don't collide."""
    from django.db.models import Q

    token = uuid.uuid4()
    base = ScheduledSend.objects.filter(status='scheduled', send_at__lte=now).filter(
        Q(claim_token__isnull=True) | Q(claim_expires_at__lt=now)
    )
    if user is not None:
        base = base.filter(user=user)

    due_ids = list(base.order_by('send_at').values_list('id', flat=True)[:MAX_DISPATCH_PER_RUN])
    if not due_ids:
        return token, []

    ScheduledSend.objects.filter(id__in=due_ids, status='scheduled').update(
        claim_token=token, claim_expires_at=now + CLAIM_TTL, updated_at=now,
    )
    return token, list(
        ScheduledSend.objects.filter(claim_token=token).values(
            'id', 'user_id', 'lead_id', 'account_id', 'subject', 'body',
        )
    )


def dispatch_due_scheduled_sends(user=None):
    """Enqueue a send_email job for every due scheduled send. Returns counts."""
    from django.contrib.auth import get_user_model
    from async_jobs.services import enqueue_job, JobQueueUnavailable

    now = timezone.now()
    token, rows = _claim_due(now, user=user)
    User = get_user_model()
    owners = {u.id: u for u in User.objects.filter(id__in={r['user_id'] for r in rows})}

    dispatched, failed = 0, 0
    for row in rows:
        owner = owners.get(row['user_id'])
        if owner is None:
            continue
        try:
            # Idempotency key ties this ScheduledSend to exactly one send job so a
            # retried beat run can never enqueue the same mail twice.
            job, _created = enqueue_job(
                owner,
                'send_email',
                {
                    'lead_id': row['lead_id'],
                    'message': row['body'],
                    'subject': row['subject'] or None,
                    'account_id': row['account_id'],
                },
                idempotency_key=f'scheduled-send-{row["id"]}',
            )
            ScheduledSend.objects.filter(id=row['id'], claim_token=token).update(
                status='dispatched', dispatched_job_id=str(job.pk),
                claim_token=None, claim_expires_at=None, updated_at=timezone.now(),
            )
            dispatched += 1
        except JobQueueUnavailable:
            # Leave it claimed; the lease expires and a later run retries.
            failed += 1
        except Exception:
            logger.exception('Failed to dispatch scheduled send %s', row['id'])
            failed += 1

    return {'dispatched': dispatched, 'failed': failed}
