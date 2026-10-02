import hashlib
import json
import logging
import re
import uuid

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import BackgroundJob

logger = logging.getLogger(__name__)

IDEMPOTENCY_KEY_RE = re.compile(r'^[A-Za-z0-9._:-]{8,128}$')


class JobQueueUnavailable(Exception):
    """Raised when the broker cannot accept background work."""


class IdempotencyConflict(Exception):
    """Raised when a caller reuses a key for a different operation."""


def request_fingerprint(job_type, payload):
    canonical = json.dumps(
        {'job_type': job_type, 'payload': payload},
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _mark_dispatch_failed(job_id):
    BackgroundJob.objects.filter(pk=job_id, status='queued').update(
        status='failed',
        error='The background worker is unavailable. Check the Redis broker and worker service, then try again.',
        finished_at=timezone.now(),
    )


def _record_dispatch_attempt(job_id):
    BackgroundJob.objects.filter(pk=job_id, status='queued').update(
        dispatch_attempts=F('dispatch_attempts') + 1,
        last_dispatched_at=timezone.now(),
    )


def _publish(job, *, fail_job_on_error=True):
    from .tasks import TASK_BY_TYPE

    try:
        TASK_BY_TYPE[job.job_type].apply_async(args=[str(job.pk)], task_id=str(job.pk))
    except Exception as exc:
        logger.exception('Could not publish background job %s', job.pk)
        _record_dispatch_attempt(job.pk)
        if fail_job_on_error:
            _mark_dispatch_failed(job.pk)
        raise JobQueueUnavailable from exc
    _record_dispatch_attempt(job.pk)


def enqueue_job(user, job_type, payload, idempotency_key=None):
    """Persist before publishing, dedupe retries, and return an owner-scoped job.

    A fresh key is generated for calls without an Idempotency-Key header. The UI
    supplies a stable key per button action so transport retries cannot enqueue
    the same send twice.
    """
    key = str(idempotency_key or uuid.uuid4())
    if not IDEMPOTENCY_KEY_RE.fullmatch(key):
        raise ValueError('Idempotency-Key must contain 8 to 128 safe characters.')

    fingerprint = request_fingerprint(job_type, payload)
    created = False
    try:
        with transaction.atomic():
            job = BackgroundJob.objects.create(
                user=user,
                job_type=job_type,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                payload=payload,
            )
            created = True
    except IntegrityError:
        job = BackgroundJob.objects.filter(user=user, idempotency_key=key).first()
        if job is None:
            # A concurrent periodic run may have won the active-job constraint.
            if job_type in ('inbox_sync', 'followup_batch'):
                job = BackgroundJob.objects.filter(
                    user=user, job_type=job_type, status__in=('queued', 'running'),
                ).first()
            if job is None:
                raise

    if job.request_fingerprint != fingerprint:
        raise IdempotencyConflict('This Idempotency-Key was already used for a different request.')

    if created:
        _publish(job)
        job.refresh_from_db()
    return job, created


def job_data(job):
    return {
        'job_id': str(job.pk),
        'job_type': job.job_type,
        'status': job.status,
        'progress': {
            'current': job.progress_current,
            'total': job.progress_total,
            'message': job.progress_message,
        },
        'result': job.result if job.status == 'succeeded' else None,
        'error': job.error or None,
        'created_at': job.created_at,
        'started_at': job.started_at,
        'finished_at': job.finished_at,
    }
