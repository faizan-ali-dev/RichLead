import json
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import BackgroundJob

logger = logging.getLogger(__name__)


class JobFailed(Exception):
    """A safe, user-displayable task failure."""


def _mark_failure(job_id, message):
    BackgroundJob.objects.filter(pk=job_id, status='running').update(
        status='failed', error=str(message)[:2000], finished_at=timezone.now(),
    )


def _execute_job(job_id, expected_type, handler, redelivered=False):
    with transaction.atomic():
        job = BackgroundJob.objects.select_for_update().filter(pk=job_id).first()
        if job is None:
            logger.error('Celery received missing background job %s', job_id)
            return
        if job.status in ('succeeded', 'failed'):
            return job.result
        if job.status == 'running':
            # A concurrent duplicate delivery must never interrupt the worker
            # that owns the job. Only a broker-marked redelivery indicates that
            # the prior worker lost its lease; even then, never replay an action
            # that may have sent mail or spent provider credits.
            if redelivered:
                job.status = 'failed'
                job.error = (
                    'A worker stopped during this operation. Check the mailbox/provider before '
                    'retrying because the external action may already have completed.'
                )
                job.finished_at = timezone.now()
                job.save(update_fields=['status', 'error', 'finished_at'])
            return
        if job.status != 'queued' or job.job_type != expected_type:
            logger.error('Invalid task/job state for %s (%s)', job_id, expected_type)
            return
        job.status = 'running'
        job.started_at = timezone.now()
        job.progress_message = 'Working'
        job.save(update_fields=['status', 'started_at', 'progress_message'])

    try:
        result = handler(job)
        if not isinstance(result, dict):
            raise TypeError('Background job handler must return a JSON object.')
        # Fail closed instead of leaving a job running if a handler returns a
        # value that the database JSON field cannot persist.
        json.dumps(result, allow_nan=False)
    except JobFailed as exc:
        _mark_failure(job_id, exc)
        return
    except Exception:
        logger.exception('Background job %s failed unexpectedly', job_id)
        _mark_failure(job_id, 'The background task failed unexpectedly. Please retry after checking its status.')
        return

    BackgroundJob.objects.filter(pk=job_id, status='running').update(
        status='succeeded', result=result, error='', finished_at=timezone.now(),
        progress_message='Completed',
    )
    return result


def update_progress(job_id, current, total, message, result=None):
    updates = {
        'progress_current': max(0, int(current)),
        'progress_total': max(0, int(total)),
        'progress_message': str(message)[:200],
    }
    if result is not None:
        json.dumps(result, allow_nan=False)
        updates['result'] = result
    BackgroundJob.objects.filter(pk=job_id, status='running').update(**updates)


def _user_for(job):
    return job.user


def _send_email(job):
    from integrations.services import send_outreach_email

    payload = job.payload
    result = send_outreach_email(
        payload['lead_id'], _user_for(job), payload['message'],
        payload.get('account_id'), payload.get('subject'),
    )
    if not result.get('success'):
        raise JobFailed(result.get('error') or 'Email could not be sent.')
    return result


def _send_email_batch(job):
    from integrations.services import send_outreach_email

    items = job.payload['items']
    sent_ids = []
    failures = []
    total = len(items)
    for index, item in enumerate(items, start=1):
        result = send_outreach_email(
            item['lead_id'], _user_for(job), item['message'],
            item.get('account_id'), item.get('subject'),
        )
        if result.get('success'):
            sent_ids.append(item['lead_id'])
        else:
            failures.append({'lead_id': item['lead_id'], 'error': result.get('error') or 'Email could not be sent.'})
        update_progress(
            job.pk, index, total, f'Processed {index} of {total} emails',
            {'sent_lead_ids': sent_ids, 'failures': failures[:25], 'sent_count': len(sent_ids), 'failed_count': len(failures)},
        )
    return {
        'success': not failures,
        'sent_lead_ids': sent_ids,
        'failures': failures[:25],
        'sent_count': len(sent_ids),
        'failed_count': len(failures),
    }


def _sync_inbox(job):
    from inbox.models import EmailMessage
    from inbox.services import sync_emails_for_user

    user = _user_for(job)
    result = sync_emails_for_user(user)
    if not result.get('success'):
        raise JobFailed('One or more mailboxes could not be synchronized. Check sender account settings and retry.')

    # Hand any freshly-arrived replies to the classifier out of band so model
    # latency never extends the sync job. Best-effort: a classification hiccup
    # must not mark a successful sync as failed.
    if EmailMessage.objects.filter(user=user, direction='inbound', intent='').exists():
        from .services import enqueue_job, JobQueueUnavailable
        try:
            enqueue_job(user, 'classify_replies', {},
                        idempotency_key=f'classify-replies:{user.id}:{timezone.now():%Y%m%d%H%M}')
        except (JobQueueUnavailable, Exception):
            logger.warning('Could not enqueue reply classification for user %s', user.id)

    return result


def _classify_replies(job):
    from ai_engine.reply_classifier import classify_pending_replies

    return classify_pending_replies(_user_for(job), limit=job.payload.get('limit'))


def _apollo_search(job):
    from integrations.apollo_service import fetch_apollo_leads

    result = fetch_apollo_leads(_user_for(job), job.payload['search_params'])
    if not result.get('success'):
        raise JobFailed(result.get('error') or 'Apollo search failed.')
    return result


def _hunter_search(job):
    from integrations.hunter_service import fetch_hunter_leads

    result = fetch_hunter_leads(_user_for(job), job.payload['search_params'])
    if not result.get('success'):
        raise JobFailed(result.get('error') or 'Hunter search failed.')
    return result


def _generate_draft(job):
    from ai_engine.services import generate_outreach_message

    result = generate_outreach_message(job.payload['lead_id'], _user_for(job))
    if not result.get('success'):
        raise JobFailed(result.get('error') or 'Draft generation failed.')
    return result


def _draft_queue(job):
    from ai_engine.services import draft_pending_leads

    result = draft_pending_leads(_user_for(job), limit=job.payload.get('limit'))
    if not result.get('success'):
        raise JobFailed(result.get('error') or 'Queue drafting failed.')
    return result


def _followup_batch(job):
    from integrations.followups import process_due_followups_for_user

    result = process_due_followups_for_user(_user_for(job))
    if not result.get('success'):
        raise JobFailed('One or more scheduled follow-ups failed. Review the sequence before retrying.')
    return result


@shared_task(bind=True, name='async_jobs.send_email', soft_time_limit=120, time_limit=180)
def send_email_task(_task, job_id):
    return _execute_job(job_id, 'send_email', _send_email, _was_redelivered(_task))


@shared_task(bind=True, name='async_jobs.send_email_batch', soft_time_limit=840, time_limit=900)
def send_email_batch_task(_task, job_id):
    return _execute_job(job_id, 'send_email_batch', _send_email_batch, _was_redelivered(_task))


@shared_task(bind=True, name='async_jobs.inbox_sync', soft_time_limit=840, time_limit=900)
def inbox_sync_task(_task, job_id):
    return _execute_job(job_id, 'inbox_sync', _sync_inbox, _was_redelivered(_task))


@shared_task(bind=True, name='async_jobs.apollo_search', soft_time_limit=840, time_limit=900)
def apollo_search_task(_task, job_id):
    return _execute_job(job_id, 'apollo_search', _apollo_search, _was_redelivered(_task))


@shared_task(bind=True, name='async_jobs.hunter_search', soft_time_limit=840, time_limit=900)
def hunter_search_task(_task, job_id):
    return _execute_job(job_id, 'hunter_search', _hunter_search, _was_redelivered(_task))


@shared_task(bind=True, name='async_jobs.generate_draft', soft_time_limit=840, time_limit=900)
def generate_draft_task(_task, job_id):
    return _execute_job(job_id, 'generate_draft', _generate_draft, _was_redelivered(_task))


@shared_task(bind=True, name='async_jobs.draft_queue', soft_time_limit=840, time_limit=900)
def draft_queue_task(_task, job_id):
    return _execute_job(job_id, 'draft_queue', _draft_queue, _was_redelivered(_task))


@shared_task(bind=True, name='async_jobs.followup_batch', soft_time_limit=840, time_limit=900)
def followup_batch_task(_task, job_id):
    return _execute_job(job_id, 'followup_batch', _followup_batch, _was_redelivered(_task))


@shared_task(bind=True, name='async_jobs.classify_replies', soft_time_limit=300, time_limit=360)
def classify_replies_task(_task, job_id):
    return _execute_job(job_id, 'classify_replies', _classify_replies, _was_redelivered(_task))


def _was_redelivered(task):
    delivery_info = getattr(task.request, 'delivery_info', None) or {}
    return bool(delivery_info.get('redelivered'))


@shared_task(name='async_jobs.prune_terminal_jobs')
def prune_terminal_jobs():
    from django.db.models import Q

    now = timezone.now()
    old_success = BackgroundJob.objects.filter(status='succeeded', finished_at__lt=now - timedelta(days=30))
    old_failure = BackgroundJob.objects.filter(status='failed', finished_at__lt=now - timedelta(days=90))
    deleted = old_success.count() + old_failure.count()
    old_success.delete()
    old_failure.delete()
    return {'deleted': deleted}


@shared_task(name='async_jobs.dispatch_queued_jobs')
def dispatch_queued_jobs():
    """Recover queued DB outbox rows if an API process died before publishing."""
    from datetime import timedelta
    from django.db.models import Q
    from .services import JobQueueUnavailable, _publish

    now = timezone.now()
    retry_before = now - timedelta(minutes=5)
    stale_dispatch = Q(last_dispatched_at__isnull=True) | Q(last_dispatched_at__lt=retry_before)
    candidates = list(
        BackgroundJob.objects.filter(status='queued', dispatch_attempts__lt=12)
        .filter(stale_dispatch)
        .order_by('created_at')[:100]
    )
    dispatched = 0
    unavailable = 0
    for job in candidates:
        try:
            _publish(job, fail_job_on_error=False)
            dispatched += 1
        except JobQueueUnavailable:
            unavailable += 1

    # Bound retries while retaining the job record and its diagnostic for the user.
    exhausted = BackgroundJob.objects.filter(
        status='queued', dispatch_attempts__gte=12, last_dispatched_at__lt=retry_before,
    )
    marked_failed = exhausted.update(
        status='failed',
        error='The background broker did not accept this job after repeated attempts. Check Redis and retry.',
        finished_at=now,
    )
    return {'dispatched': dispatched, 'broker_unavailable': unavailable, 'marked_failed': marked_failed}


TASK_BY_TYPE = {
    'send_email': send_email_task,
    'send_email_batch': send_email_batch_task,
    'inbox_sync': inbox_sync_task,
    'apollo_search': apollo_search_task,
    'hunter_search': hunter_search_task,
    'generate_draft': generate_draft_task,
    'draft_queue': draft_queue_task,
    'followup_batch': followup_batch_task,
    'classify_replies': classify_replies_task,
}
