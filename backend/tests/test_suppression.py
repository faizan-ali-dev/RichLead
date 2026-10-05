"""P0-2: suppression must be enforced on send and must never be erased."""
import pytest

from leads.models import Lead
from integrations.services import send_outreach_email


@pytest.mark.django_db
def test_blacklisted_lead_is_never_emailed(user_a, lead_a):
    lead_a.status = 'blacklisted'
    lead_a.save()

    result = send_outreach_email(lead_a.id, user_a, "hello")

    assert result['success'] is False
    assert 'suppress' in result['error'].lower() or 'blacklist' in result['error'].lower()


@pytest.mark.django_db
def test_blacklist_survives_a_send_attempt(user_a, lead_a):
    """The original bug silently rewrote 'blacklisted' to 'reached', erasing the opt-out."""
    lead_a.status = 'blacklisted'
    lead_a.save()

    send_outreach_email(lead_a.id, user_a, "hello")

    lead_a.refresh_from_db()
    assert lead_a.status == 'blacklisted'


@pytest.mark.django_db
def test_suppressed_email_blocks_send_even_when_status_is_pending(user_a, lead_a):
    from integrations.models import SuppressionEntry

    SuppressionEntry.objects.create(user=user_a, email=lead_a.email, reason='unsubscribed')

    result = send_outreach_email(lead_a.id, user_a, "hello")
    assert result['success'] is False
    lead_a.refresh_from_db()
    assert lead_a.status != 'reached'


@pytest.mark.django_db
def test_suppression_is_case_insensitive(user_a, lead_a):
    from integrations.models import SuppressionEntry

    SuppressionEntry.objects.create(user=user_a, email=lead_a.email.upper(), reason='unsubscribed')

    result = send_outreach_email(lead_a.id, user_a, "hello")
    assert result['success'] is False


@pytest.mark.django_db
def test_suppression_is_scoped_per_tenant(user_a, user_b, lead_a, settings):
    """User B suppressing an address must not block User A from contacting them."""
    from integrations.models import SuppressionEntry

    settings.ALLOW_SANDBOX_SEND = True

    SuppressionEntry.objects.create(user=user_b, email=lead_a.email, reason='unsubscribed')

    result = send_outreach_email(lead_a.id, user_a, "hello")
    assert result['success'] is True


@pytest.mark.django_db
def test_replied_status_does_not_regress_to_reached(user_a, lead_a, settings):
    """A follow-up must not wipe the fact that the lead already replied."""
    settings.ALLOW_SANDBOX_SEND = True
    lead_a.status = 'replied'
    lead_a.save()

    send_outreach_email(lead_a.id, user_a, "following up")

    lead_a.refresh_from_db()
    assert lead_a.status == 'replied'


@pytest.mark.django_db
def test_suppression_api_round_trip(auth_a, user_a):
    resp = auth_a.post('/api/integrations/suppression/', {'email': 'NoMail@Example.test'}, format='json')
    assert resp.status_code == 201

    listed = auth_a.get('/api/integrations/suppression/')
    assert listed.status_code == 200
    rows = listed.json()
    rows = rows['results'] if isinstance(rows, dict) else rows
    assert any(r['email'] == 'nomail@example.test' for r in rows)


@pytest.mark.django_db
def test_suppression_list_is_tenant_scoped(auth_a, auth_b):
    auth_a.post('/api/integrations/suppression/', {'email': 'a-only@example.test'}, format='json')

    rows = auth_b.get('/api/integrations/suppression/').json()
    rows = rows['results'] if isinstance(rows, dict) else rows
    assert rows == []
