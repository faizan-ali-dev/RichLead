"""Feature 2: send-time optimization."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from integrations.models import ScheduledSend, SendingWindow
from integrations.scheduled_sends import compute_send_at, dispatch_due_scheduled_sends, schedule_send
from integrations.sendtime import UTC, infer_timezone, next_send_time
from leads.models import Lead


# --------------------------------------------------------------------------
# Timezone inference (pure)
# --------------------------------------------------------------------------

def test_infer_timezone_from_city():
    assert infer_timezone('San Francisco, CA') == ZoneInfo('America/Los_Angeles')
    assert infer_timezone('London, UK') == ZoneInfo('Europe/London')
    assert infer_timezone('Bangalore, India') == ZoneInfo('Asia/Kolkata')


def test_infer_timezone_longest_keyword_wins():
    # "new york" must beat a bare "york" if both were present.
    assert infer_timezone('New York City') == ZoneInfo('America/New_York')


def test_infer_timezone_falls_back_when_unknown():
    assert infer_timezone('Atlantis', default='Europe/Paris') == ZoneInfo('Europe/Paris')
    assert infer_timezone('') == UTC


def test_infer_timezone_bad_default_is_utc():
    assert infer_timezone('nowhere', default='Not/AZone') == UTC


# --------------------------------------------------------------------------
# Next-slot computation (pure)
# --------------------------------------------------------------------------

class _Window:
    def __init__(self, earliest=8, latest=17, weekdays_only=True):
        self.earliest_hour = earliest
        self.latest_hour = latest
        self.weekdays_only = weekdays_only


def test_inside_window_sends_now():
    tz = ZoneInfo('America/New_York')
    # Wed 10:00 EST (15:00 UTC)
    now = datetime(2026, 1, 7, 15, 0, tzinfo=UTC)
    assert next_send_time(_Window(), tz, now=now) == now


def test_before_opening_waits_for_opening():
    tz = ZoneInfo('America/New_York')
    # Wed 05:00 EST (10:00 UTC) -> opening is 08:00 EST same day (13:00 UTC)
    now = datetime(2026, 1, 7, 10, 0, tzinfo=UTC)
    result = next_send_time(_Window(), tz, now=now)
    assert result.astimezone(tz).hour == 8
    assert result.astimezone(tz).date() == now.astimezone(tz).date()


def test_after_close_rolls_to_next_morning():
    tz = ZoneInfo('America/New_York')
    # Wed 20:00 EST -> next morning Thu 08:00 EST
    now = datetime(2026, 1, 7, 1, 0, tzinfo=UTC)  # Tue 20:00 EST
    result = next_send_time(_Window(), tz, now=now)
    local = result.astimezone(tz)
    assert local.hour == 8
    assert local.weekday() == 2  # Wednesday


def test_weekend_is_skipped():
    tz = ZoneInfo('America/New_York')
    # Saturday 10:00 EST -> next opening is Monday 08:00
    now = datetime(2026, 1, 10, 15, 0, tzinfo=UTC)  # Sat
    result = next_send_time(_Window(weekdays_only=True), tz, now=now)
    assert result.astimezone(tz).weekday() == 0  # Monday


def test_weekend_allowed_when_not_weekdays_only():
    tz = ZoneInfo('America/New_York')
    now = datetime(2026, 1, 10, 15, 0, tzinfo=UTC)  # Sat 10:00 EST, inside window
    result = next_send_time(_Window(weekdays_only=False), tz, now=now)
    assert result == now


# --------------------------------------------------------------------------
# Scheduling + dispatch (integration)
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_schedule_send_creates_a_future_row(user_a, lead_a):
    lead_a.location = 'London, UK'
    lead_a.save()

    scheduled = schedule_send(
        user_a, lead_a, 'A draft. Worth a look?',
        subject='a subject', now=datetime(2026, 1, 7, 1, 0, tzinfo=UTC),  # 01:00 London
    )
    assert scheduled.status == 'scheduled'
    assert scheduled.recipient_timezone == 'Europe/London'
    assert scheduled.send_at.astimezone(ZoneInfo('Europe/London')).hour == 8


@pytest.mark.django_db
def test_scheduling_again_replaces_the_previous(user_a, lead_a):
    schedule_send(user_a, lead_a, 'first')
    schedule_send(user_a, lead_a, 'second')
    active = ScheduledSend.objects.filter(user=user_a, lead=lead_a, status='scheduled')
    assert active.count() == 1
    assert active.first().body == 'second'


@pytest.mark.django_db
def test_schedule_endpoint(auth_a, user_a, lead_a):
    resp = auth_a.post('/api/integrations/schedule-send/', {
        'lead_id': lead_a.id, 'message': 'A draft. Worth a look?', 'subject': 's',
    }, format='json')
    assert resp.status_code == 201
    assert resp.json()['success'] is True
    assert ScheduledSend.objects.filter(user=user_a, lead=lead_a).count() == 1


@pytest.mark.django_db
def test_cannot_schedule_a_blacklisted_lead(auth_a, user_a, lead_a):
    lead_a.status = 'blacklisted'
    lead_a.save()
    resp = auth_a.post('/api/integrations/schedule-send/',
                       {'lead_id': lead_a.id, 'message': 'x'}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_due_sends_are_dispatched_to_the_send_pipeline(user_a, lead_a, monkeypatch):
    # A past send_at makes it immediately due.
    ScheduledSend.objects.create(
        user=user_a, lead=lead_a, body='A draft. Worth a look?', subject='s',
        send_at=datetime(2020, 1, 1, tzinfo=UTC),
    )

    enqueued = []

    def fake_enqueue(user, job_type, payload, idempotency_key=None):
        enqueued.append((job_type, payload, idempotency_key))

        class _Job:
            pk = 'job-123'
        return _Job(), True

    monkeypatch.setattr('async_jobs.services.enqueue_job', fake_enqueue)
    result = dispatch_due_scheduled_sends(user=user_a)

    assert result['dispatched'] == 1
    assert enqueued[0][0] == 'send_email'
    assert enqueued[0][1]['lead_id'] == lead_a.id
    assert enqueued[0][2] == f'scheduled-send-{ScheduledSend.objects.get().pk}'

    ScheduledSend.objects.get().refresh_from_db()
    assert ScheduledSend.objects.get().status == 'dispatched'


@pytest.mark.django_db
def test_future_sends_are_not_dispatched(user_a, lead_a, monkeypatch):
    from django.utils import timezone as djtz
    from datetime import timedelta

    ScheduledSend.objects.create(
        user=user_a, lead=lead_a, body='x', send_at=djtz.now() + timedelta(hours=5),
    )
    monkeypatch.setattr('async_jobs.services.enqueue_job',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('should not dispatch')))
    assert dispatch_due_scheduled_sends(user=user_a)['dispatched'] == 0


@pytest.mark.django_db
def test_window_endpoint_round_trip(auth_a):
    resp = auth_a.patch('/api/integrations/sending-window/', {
        'optimize_send_time': True, 'earliest_hour': 9, 'latest_hour': 16,
    }, format='json')
    assert resp.status_code == 200
    assert resp.json()['optimize_send_time'] is True
    assert resp.json()['earliest_hour'] == 9


@pytest.mark.django_db
def test_window_rejects_inverted_hours(auth_a):
    resp = auth_a.patch('/api/integrations/sending-window/',
                        {'earliest_hour': 17, 'latest_hour': 9}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_window_rejects_bad_timezone(auth_a):
    resp = auth_a.patch('/api/integrations/sending-window/',
                        {'fallback_timezone': 'Not/AZone'}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_window_is_tenant_scoped(auth_a, auth_b):
    auth_a.patch('/api/integrations/sending-window/', {'optimize_send_time': True}, format='json')
    assert auth_b.get('/api/integrations/sending-window/').json()['optimize_send_time'] is False


@pytest.mark.django_db
def test_compute_send_at_uses_fallback_tz_when_location_unknown(user_a, lead_a):
    SendingWindow.objects.create(user=user_a, fallback_timezone='Asia/Tokyo')
    lead_a.location = ''
    lead_a.save()
    _, tz_name = compute_send_at(user_a, lead_a)
    assert tz_name == 'Asia/Tokyo'
