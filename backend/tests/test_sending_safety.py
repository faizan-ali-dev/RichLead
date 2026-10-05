"""P2/P3: sending must not lie, must not exceed provider limits, and must be revocable."""
import pytest
from django.utils import timezone

from integrations.models import EmailAccount
from integrations.services import send_outreach_email
from leads.models import Lead


@pytest.mark.django_db
def test_send_without_a_connected_account_fails_loudly(user_a, lead_a):
    """Mock mode used to return success and mark the lead 'reached', so users
    believed campaigns were running while nothing was sent."""
    result = send_outreach_email(lead_a.id, user_a, "hello")

    assert result['success'] is False
    assert 'no connected' in result['error'].lower() or 'sender' in result['error'].lower()

    lead_a.refresh_from_db()
    assert lead_a.status == 'pending'
    assert lead_a.first_sent_at is None


@pytest.mark.django_db
def test_sandbox_mode_is_opt_in_and_marked(user_a, lead_a, settings):
    settings.ALLOW_SANDBOX_SEND = True

    result = send_outreach_email(lead_a.id, user_a, "hello")

    assert result['success'] is True
    assert result.get('sandbox') is True


@pytest.mark.django_db
def test_daily_cap_blocks_further_sends(user_a, lead_a):
    """An exhausted mailbox must refuse before touching the network."""
    account = EmailAccount.objects.create(
        user=user_a, email_address='s@x.test', auth_type='smtp',
        smtp_host='smtp.x.test', is_connected=True,
        daily_send_limit=2, sends_today=2, sends_counted_on=timezone.now().date(),
    )
    assert account.remaining_sends_today() == 0

    result = send_outreach_email(lead_a.id, user_a, "hi", account_id=account.id)

    assert result['success'] is False
    assert 'limit' in result['error'].lower()
    lead_a.refresh_from_db()
    assert lead_a.first_sent_at is None


@pytest.mark.django_db
def test_record_send_increments_the_daily_counter(user_a):
    account = EmailAccount.objects.create(
        user=user_a, email_address='s@x.test', auth_type='smtp',
        is_connected=True, daily_send_limit=5,
    )
    assert account.remaining_sends_today() == 5

    account.record_send()
    account.refresh_from_db()
    assert account.sends_today == 1
    assert account.remaining_sends_today() == 4


@pytest.mark.django_db
def test_exhausted_accounts_are_skipped_by_rotation(user_a):
    from integrations.services import pick_sending_account

    EmailAccount.objects.create(
        user=user_a, email_address='full@x.test', auth_type='smtp', is_connected=True,
        daily_send_limit=1, sends_today=1, sends_counted_on=timezone.now().date(),
    )
    assert pick_sending_account(user_a) is None


@pytest.mark.django_db
def test_daily_counter_resets_on_a_new_day(user_a):
    account = EmailAccount.objects.create(
        user=user_a, email_address='s@x.test', auth_type='smtp',
        is_connected=True, daily_send_limit=1,
        sends_today=1, sends_counted_on=timezone.now().date() - timezone.timedelta(days=1),
    )
    assert account.remaining_sends_today() == 1


@pytest.mark.django_db
def test_rotation_picks_the_least_loaded_account(user_a):
    busy = EmailAccount.objects.create(
        user=user_a, email_address='busy@x.test', auth_type='smtp', is_connected=True,
        sends_today=20, sends_counted_on=timezone.now().date(),
    )
    idle = EmailAccount.objects.create(
        user=user_a, email_address='idle@x.test', auth_type='smtp', is_connected=True,
        sends_today=0, sends_counted_on=timezone.now().date(),
    )

    from integrations.services import pick_sending_account
    assert pick_sending_account(user_a).id == idle.id


@pytest.mark.django_db
def test_unsubscribe_token_round_trips(user_a, lead_a):
    from integrations.unsubscribe import make_token, resolve_token

    token = make_token(user_a.id, lead_a.id)
    assert resolve_token(token) == (user_a.id, lead_a.id)


@pytest.mark.django_db
def test_tampered_unsubscribe_token_is_rejected():
    from integrations.unsubscribe import resolve_token

    assert resolve_token('bogus') is None


@pytest.mark.django_db
def test_unsubscribe_endpoint_suppresses_the_lead(api, user_a, lead_a):
    from integrations.models import SuppressionEntry
    from integrations.unsubscribe import make_token

    token = make_token(user_a.id, lead_a.id)
    resp = api.get(f'/api/integrations/unsubscribe/{token}/')

    assert resp.status_code == 200
    assert SuppressionEntry.objects.filter(user=user_a, email=lead_a.email).exists()

    lead_a.refresh_from_db()
    assert lead_a.status == 'blacklisted'


@pytest.mark.django_db
def test_leads_list_does_not_n_plus_one(auth_a, user_a, django_assert_max_num_queries):
    from leads.models import AIResearch, IntentSignal, ScoreBreakdown

    for i in range(10):
        lead = Lead.objects.create(user=user_a, name=f"L{i}", company="C", niche="n", email=f"n{i}@x.test")
        AIResearch.objects.create(lead=lead, summary='s', generated_message='m')
        IntentSignal.objects.create(lead=lead, signal='sig')
        ScoreBreakdown.objects.create(lead=lead, factor='f', score=1, max_score=2)

    # Prefetching means query count stays flat regardless of row count.
    with django_assert_max_num_queries(10):
        auth_a.get('/api/leads/')


@pytest.mark.django_db
def test_inbox_list_does_not_n_plus_one(auth_a, user_a, django_assert_max_num_queries):
    from inbox.models import EmailMessage

    for i in range(10):
        lead = Lead.objects.create(user=user_a, name=f"L{i}", company="C", niche="n", email=f"i{i}@x.test")
        EmailMessage.objects.create(
            user=user_a, lead=lead, message_id=f"<m{i}@x.test>",
            from_email='a@x.test', to_email='b@x.test', received_at=timezone.now(),
        )

    with django_assert_max_num_queries(10):
        auth_a.get('/api/inbox/')


@pytest.mark.django_db
def test_research_and_draft_endpoint_exists(auth_a, lead_a):
    """The Leads page calls this; it used to 404."""
    resp = auth_a.post('/api/ai/research-and-draft/', {'lead_id': lead_a.id}, format='json')
    assert resp.status_code != 404
