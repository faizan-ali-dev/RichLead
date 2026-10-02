from unittest.mock import Mock

import pytest

from async_jobs.models import BackgroundJob
from async_jobs.tasks import _execute_job


@pytest.mark.django_db
def test_send_endpoint_queues_once_and_job_status_is_tenant_scoped(auth_a, auth_b, lead_a, monkeypatch):
    from async_jobs.tasks import send_email_task

    publish = Mock()
    monkeypatch.setattr(send_email_task, 'apply_async', publish)
    headers = {'HTTP_IDEMPOTENCY_KEY': 'send-lead-once-001'}
    payload = {'lead_id': lead_a.pk, 'message': 'A reviewed outreach message.'}

    response = auth_a.post('/api/integrations/send-email/', payload, format='json', **headers)
    assert response.status_code == 202
    job_id = response.data['job_id']
    assert response.data['status'] == 'queued'
    publish.assert_called_once_with(args=[job_id], task_id=job_id)

    duplicate = auth_a.post('/api/integrations/send-email/', payload, format='json', **headers)
    assert duplicate.status_code == 202
    assert duplicate.data['job_id'] == job_id
    publish.assert_called_once()
    job = BackgroundJob.objects.get(pk=job_id)
    assert job.user_id == lead_a.user_id
    assert job.payload['lead_id'] == lead_a.pk

    assert auth_a.get(f'/api/jobs/{job_id}/').status_code == 200
    assert auth_b.get(f'/api/jobs/{job_id}/').status_code == 404


@pytest.mark.django_db
def test_idempotency_key_cannot_be_reused_for_a_different_request(auth_a, lead_a, monkeypatch):
    from async_jobs.tasks import send_email_task

    publish = Mock()
    monkeypatch.setattr(send_email_task, 'apply_async', publish)
    headers = {'HTTP_IDEMPOTENCY_KEY': 'same-action-key-001'}
    url = '/api/integrations/send-email/'
    assert auth_a.post(url, {'lead_id': lead_a.pk, 'message': 'First body'}, format='json', **headers).status_code == 202
    response = auth_a.post(url, {'lead_id': lead_a.pk, 'message': 'Changed body'}, format='json', **headers)
    assert response.status_code == 409
    publish.assert_called_once()


@pytest.mark.django_db
def test_durable_outbox_dispatches_job_after_api_publish_was_interrupted(user_a, monkeypatch):
    from async_jobs.tasks import dispatch_queued_jobs
    from async_jobs import services

    job = BackgroundJob.objects.create(
        user=user_a,
        job_type='generate_draft',
        idempotency_key='outbox-recovery-001',
        request_fingerprint='c' * 64,
        payload={'lead_id': 1},
    )
    publish = Mock()
    monkeypatch.setattr(services, '_publish', publish)

    result = dispatch_queued_jobs.run()

    assert result['dispatched'] == 1
    publish.assert_called_once_with(job, fail_job_on_error=False)


@pytest.mark.django_db
def test_background_job_handler_is_single_execution_even_if_celery_redelivers(user_a):
    job = BackgroundJob.objects.create(
        user=user_a,
        job_type='generate_draft',
        idempotency_key='single-execution-001',
        request_fingerprint='f' * 64,
        payload={'lead_id': 1},
    )
    handler = Mock(return_value={'success': True, 'message': 'Draft'})

    _execute_job(str(job.pk), 'generate_draft', handler)
    _execute_job(str(job.pk), 'generate_draft', handler)

    job.refresh_from_db()
    assert job.status == 'succeeded'
    assert job.result['message'] == 'Draft'
    handler.assert_called_once()


@pytest.mark.django_db
def test_duplicate_delivery_does_not_interrupt_worker_owning_send(user_a):
    job = BackgroundJob.objects.create(
        user=user_a,
        job_type='send_email',
        status='running',
        idempotency_key='interrupted-send-001',
        request_fingerprint='a' * 64,
        payload={'lead_id': 1, 'message': 'Already sent or uncertain'},
    )
    handler = Mock()

    _execute_job(str(job.pk), 'send_email', handler)

    job.refresh_from_db()
    assert job.status == 'running'
    handler.assert_not_called()


@pytest.mark.django_db
def test_redelivered_running_send_is_failed_without_replaying(user_a):
    job = BackgroundJob.objects.create(
        user=user_a,
        job_type='send_email',
        status='running',
        idempotency_key='redelivered-send-001',
        request_fingerprint='b' * 64,
        payload={'lead_id': 1, 'message': 'Already sent or uncertain'},
    )
    handler = Mock()

    _execute_job(str(job.pk), 'send_email', handler, redelivered=True)

    job.refresh_from_db()
    assert job.status == 'failed'
    assert 'may already have completed' in job.error
    handler.assert_not_called()


@pytest.mark.django_db
def test_successful_first_touch_creates_configured_followup_sequence(user_a, lead_a):
    from ai_engine.models import FollowUpSettings
    from integrations.followups import schedule_followup_after_first_touch
    from integrations.models import FollowUpSequence
    from django.utils import timezone
    from datetime import timedelta

    FollowUpSettings.objects.create(user=user_a, enabled=True, total_follow_ups=2, days_between=3)
    sent_at = timezone.now()

    sequence = schedule_followup_after_first_touch(user_a, lead_a, sent_at=sent_at)

    assert isinstance(sequence, FollowUpSequence)
    assert sequence.sent_follow_ups == 0
    assert sequence.next_send_at == sent_at + timedelta(days=3)


@pytest.mark.django_db
def test_reply_thread_does_not_start_a_new_automated_sequence(user_a, lead_a):
    from django.utils import timezone
    from inbox.models import EmailMessage
    from integrations.followups import schedule_followup_after_first_touch

    EmailMessage.objects.create(
        user=user_a, lead=lead_a, message_id='reply-thread-inbound', direction='inbound',
        from_email=lead_a.email, to_email=user_a.email, subject='Re: hello',
        body_text='Thanks, send more information.', received_at=timezone.now(),
    )

    assert schedule_followup_after_first_touch(user_a, lead_a) is None


@pytest.mark.django_db
def test_scheduled_followup_stops_after_a_synced_reply(user_a, lead_a):
    from datetime import timedelta
    from django.utils import timezone
    from ai_engine.models import FollowUpSettings
    from inbox.models import EmailMessage
    from integrations.followups import process_due_followups_for_user
    from integrations.models import FollowUpSequence

    now = timezone.now()
    FollowUpSettings.objects.create(user=user_a, enabled=True, total_follow_ups=2, days_between=3, stop_on_reply=True)
    FollowUpSequence.objects.create(
        user=user_a,
        lead=lead_a,
        sent_follow_ups=0,
        last_sent_at=now - timedelta(days=4),
        next_send_at=now - timedelta(minutes=1),
    )
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, message_id='previous-outbound', direction='outbound',
        from_email=user_a.email, to_email=lead_a.email, subject='Can we help?',
        body_text='The first reviewed message.', received_at=now - timedelta(days=4),
    )
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, message_id='reply-from-prospect', direction='inbound',
        from_email=lead_a.email, to_email=user_a.email, subject='Re: Can we help?',
        body_text='Yes, please send more details.', received_at=now - timedelta(days=2),
    )

    result = process_due_followups_for_user(user_a)

    sequence = FollowUpSequence.objects.get(lead=lead_a)
    assert result['stopped'] == 1
    assert sequence.status == 'stopped'
