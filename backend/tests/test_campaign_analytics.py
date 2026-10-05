"""Feature 5: per-campaign and per-mailbox funnel analytics."""
import pytest
from django.utils import timezone

from inbox.models import EmailMessage
from integrations.models import EmailAccount
from leads.analytics import campaign_funnels, mailbox_funnels
from leads.models import Lead


def _lead(user, tag, **kw):
    return Lead.objects.create(user=user, name='L', company='C', niche='n',
                               email=f'{tag}@x.test', **kw)


def _account(user, email):
    acc = EmailAccount.objects.create(user=user, email_address=email, auth_type='smtp', is_connected=True)
    acc.set_password('pw')
    acc.save()
    return acc


def _outbound(user, lead, account, when=None):
    return EmailMessage.objects.create(
        user=user, lead=lead, account=account,
        message_id=f'<{lead.email}-{timezone.now().timestamp()}@x.test>',
        from_email=account.email_address, to_email=lead.email, subject='s',
        received_at=when or timezone.now(), direction='outbound',
    )


# --------------------------------------------------------------------------
# Campaign funnels
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_campaign_funnel_groups_by_campaign(user_a):
    now = timezone.now()
    _lead(user_a, 'c1', campaign='Q1 SaaS', first_sent_at=now, replied_at=now)
    _lead(user_a, 'c2', campaign='Q1 SaaS', first_sent_at=now)
    _lead(user_a, 'c3', campaign='Q1 SaaS')  # pending

    funnels = {f['label']: f for f in campaign_funnels(user_a)}
    q1 = funnels['Q1 SaaS']
    assert q1['total'] == 3
    assert q1['sent'] == 2
    assert q1['replied'] == 1
    assert q1['pending'] == 1
    assert q1['reply_rate'] == 0.5


@pytest.mark.django_db
def test_campaign_falls_back_to_source(user_a):
    now = timezone.now()
    _lead(user_a, 's1', source='apollo', first_sent_at=now)
    _lead(user_a, 's2', source='hunter', first_sent_at=now, replied_at=now)

    labels = {f['label'] for f in campaign_funnels(user_a)}
    assert 'apollo' in labels and 'hunter' in labels


@pytest.mark.django_db
def test_campaign_blank_is_uncategorized(user_a):
    _lead(user_a, 'u1')  # no campaign, no source
    funnels = campaign_funnels(user_a)
    assert any(f['label'] == 'Uncategorized' for f in funnels)


@pytest.mark.django_db
def test_campaign_funnels_sorted_by_volume(user_a):
    now = timezone.now()
    for i in range(3):
        _lead(user_a, f'big{i}', campaign='Big', first_sent_at=now)
    _lead(user_a, 'small', campaign='Small', first_sent_at=now)

    funnels = campaign_funnels(user_a)
    assert funnels[0]['label'] == 'Big'


@pytest.mark.django_db
def test_campaign_analytics_is_tenant_scoped(user_a, user_b):
    _lead(user_b, 'theirs', campaign='Theirs', first_sent_at=timezone.now())
    assert campaign_funnels(user_a) == []


# --------------------------------------------------------------------------
# Mailbox funnels
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_mailbox_funnel_attributes_sends_and_replies(user_a):
    now = timezone.now()
    acc1 = _account(user_a, 'inbox1@acme.test')
    acc2 = _account(user_a, 'inbox2@acme.test')

    l1 = _lead(user_a, 'm1', first_sent_at=now, replied_at=now)
    l2 = _lead(user_a, 'm2', first_sent_at=now)
    l3 = _lead(user_a, 'm3', first_sent_at=now)
    _outbound(user_a, l1, acc1)
    _outbound(user_a, l2, acc1)
    _outbound(user_a, l3, acc2)

    funnels = {f['label']: f for f in mailbox_funnels(user_a)}
    assert funnels['inbox1@acme.test']['sent'] == 2
    assert funnels['inbox1@acme.test']['replied'] == 1
    assert funnels['inbox1@acme.test']['reply_rate'] == 0.5
    assert funnels['inbox2@acme.test']['sent'] == 1
    assert funnels['inbox2@acme.test']['replied'] == 0


@pytest.mark.django_db
def test_mailbox_funnel_uses_first_touch_account(user_a):
    now = timezone.now()
    acc1 = _account(user_a, 'first@acme.test')
    acc2 = _account(user_a, 'second@acme.test')
    lead = _lead(user_a, 'ft', first_sent_at=now, replied_at=now)

    _outbound(user_a, lead, acc1, when=now)
    _outbound(user_a, lead, acc2, when=now + timezone.timedelta(days=1))  # follow-up from a different inbox

    funnels = {f['label']: f for f in mailbox_funnels(user_a)}
    # The lead counts once, under its first-touch inbox only.
    assert funnels['first@acme.test']['sent'] == 1
    assert 'second@acme.test' not in funnels


@pytest.mark.django_db
def test_mailbox_funnel_empty_without_sends(user_a):
    assert mailbox_funnels(user_a) == []


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_analytics_endpoint(auth_a, user_a):
    now = timezone.now()
    _lead(user_a, 'api1', campaign='Launch', first_sent_at=now, replied_at=now)

    resp = auth_a.get('/api/analytics/campaigns/')
    assert resp.status_code == 200
    data = resp.json()
    assert 'campaigns' in data and 'mailboxes' in data
    assert any(c['label'] == 'Launch' for c in data['campaigns'])


@pytest.mark.django_db
def test_analytics_requires_authentication(api):
    assert api.get('/api/analytics/campaigns/').status_code in (401, 403)


@pytest.mark.django_db
def test_campaign_tag_round_trips_via_lead_api(auth_a, user_a):
    resp = auth_a.post('/api/leads/', {
        'name': 'Carol', 'company': 'Globex', 'niche': 'SaaS',
        'email': 'tag@globex.test', 'campaign': 'Spring Outreach',
    }, format='json')
    assert resp.status_code == 201
    lead = Lead.objects.get(user=user_a, email='tag@globex.test')
    assert lead.campaign == 'Spring Outreach'
