"""P1: dashboard metrics must be arithmetically correct.

The original counted sends as status=='reached', but a reply moves the lead out of
that bucket -- so the denominator excluded exactly the successes being measured.
10 sent / 10 replied reported 0%.
"""
import pytest
from django.utils import timezone

from leads.models import Lead


def _lead(user, i, **kw):
    return Lead.objects.create(
        user=user, name=f"L{i}", company="C", niche="n", email=f"stat{i}@x.test", **kw
    )


@pytest.mark.django_db
def test_all_replied_reports_100_percent(auth_a, user_a):
    now = timezone.now()
    for i in range(10):
        _lead(user_a, i, status='replied', first_sent_at=now, replied_at=now)

    stats = auth_a.get('/api/dashboard/stats/').json()

    assert stats['messages_sent'] == 10
    assert stats['replies'] == 10
    assert stats['reply_rate'] == '100.0%'


@pytest.mark.django_db
def test_partial_replies_use_total_sent_as_denominator(auth_a, user_a):
    now = timezone.now()
    for i in range(8):
        _lead(user_a, i, status='reached', first_sent_at=now)
    for i in range(8, 10):
        _lead(user_a, i, status='replied', first_sent_at=now, replied_at=now)

    stats = auth_a.get('/api/dashboard/stats/').json()

    assert stats['messages_sent'] == 10
    assert stats['replies'] == 2
    assert stats['reply_rate'] == '20.0%'


@pytest.mark.django_db
def test_no_sends_reports_zero_not_division_error(auth_a, user_a):
    _lead(user_a, 1)
    stats = auth_a.get('/api/dashboard/stats/').json()
    assert stats['reply_rate'] == '0.0%'


@pytest.mark.django_db
def test_messages_generated_ignores_blank_drafts(auth_a, user_a):
    from leads.models import AIResearch

    lead_with = _lead(user_a, 1)
    lead_blank = _lead(user_a, 2)
    AIResearch.objects.create(lead=lead_with, summary='s', generated_message='Hi there')
    AIResearch.objects.create(lead=lead_blank, summary='s', generated_message='')

    stats = auth_a.get('/api/dashboard/stats/').json()

    assert stats['ai_researched'] == 2
    assert stats['messages_generated'] == 1


@pytest.mark.django_db
def test_stats_are_tenant_scoped(auth_a, user_b):
    now = timezone.now()
    _lead(user_b, 1, status='replied', first_sent_at=now, replied_at=now)

    stats = auth_a.get('/api/dashboard/stats/').json()
    assert stats['leads_discovered'] == 0


@pytest.mark.django_db
def test_stats_use_a_bounded_number_of_queries(auth_a, user_a, django_assert_max_num_queries):
    now = timezone.now()
    for i in range(20):
        _lead(user_a, i, status='reached', first_sent_at=now)

    # The dashboard builds the counters (one aggregate), a 7-day send/reply/bounce
    # chart, and a recent-activity feed. That is a fixed set of queries regardless
    # of lead volume -- the guard is against an N+1 that scales with the 20 leads,
    # not against this constant overhead.
    with django_assert_max_num_queries(10):
        auth_a.get('/api/dashboard/stats/')


@pytest.mark.django_db
def test_sending_records_first_sent_at(user_a, lead_a, settings):
    from integrations.services import send_outreach_email

    settings.ALLOW_SANDBOX_SEND = True

    assert lead_a.first_sent_at is None
    send_outreach_email(lead_a.id, user_a, "hello")

    lead_a.refresh_from_db()
    assert lead_a.first_sent_at is not None


@pytest.mark.django_db
def test_first_sent_at_is_not_overwritten_by_follow_ups(user_a, lead_a, settings):
    from integrations.services import send_outreach_email

    settings.ALLOW_SANDBOX_SEND = True

    send_outreach_email(lead_a.id, user_a, "first")
    lead_a.refresh_from_db()
    original = lead_a.first_sent_at

    send_outreach_email(lead_a.id, user_a, "follow up")
    lead_a.refresh_from_db()
    assert lead_a.first_sent_at == original
