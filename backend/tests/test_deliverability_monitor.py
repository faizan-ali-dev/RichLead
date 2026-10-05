"""Feature 6: SPF/DKIM/DMARC monitoring with drift alerts."""
import pytest

from integrations import deliverability
from integrations.models import DomainDeliverability, EmailAccount


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _account(user, email):
    acc = EmailAccount.objects.create(user=user, email_address=email, auth_type='smtp', is_connected=True)
    acc.set_password('pw')
    acc.save()
    return acc


def _fake_dns(mapping):
    """Return a _txt_records stand-in backed by `mapping` {name: [records]}.

    A name absent from the mapping resolves to an empty list (no record);
    a value of None simulates a lookup error.
    """
    def _lookup(name):
        return mapping.get(name, [])
    return _lookup


# --------------------------------------------------------------------------
# Record grading
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_healthy_domain(monkeypatch):
    monkeypatch.setattr(deliverability, '_txt_records', _fake_dns({
        'acme.test': ['v=spf1 include:_spf.google.com ~all'],
        '_dmarc.acme.test': ['v=DMARC1; p=reject; rua=mailto:dmarc@acme.test'],
        'google._domainkey.acme.test': ['v=DKIM1; k=rsa; p=MIGf...'],
    }))
    result = deliverability.check_domain('acme.test')
    assert result['status'] == 'healthy'
    assert result['spf_status'] == 'pass'
    assert result['dmarc_status'] == 'pass'
    assert result['dmarc_policy'] == 'reject'
    assert result['dkim_status'] == 'found'
    assert result['dkim_selectors'] == ['google']
    assert result['issues'] == []


@pytest.mark.django_db
def test_missing_spf_is_failing(monkeypatch):
    monkeypatch.setattr(deliverability, '_txt_records', _fake_dns({
        '_dmarc.acme.test': ['v=DMARC1; p=quarantine'],
    }))
    result = deliverability.check_domain('acme.test')
    assert result['spf_status'] == 'missing'
    assert result['status'] == 'failing'
    assert any('SPF' in issue for issue in result['issues'])


@pytest.mark.django_db
def test_dmarc_p_none_is_at_risk(monkeypatch):
    monkeypatch.setattr(deliverability, '_txt_records', _fake_dns({
        'acme.test': ['v=spf1 -all'],
        '_dmarc.acme.test': ['v=DMARC1; p=none'],
        'google._domainkey.acme.test': ['v=DKIM1; p=abc'],
    }))
    result = deliverability.check_domain('acme.test')
    assert result['dmarc_policy'] == 'none'
    assert result['status'] == 'at_risk'
    assert any('p=none' in issue for issue in result['issues'])


@pytest.mark.django_db
def test_dns_error_degrades_not_raises(monkeypatch):
    monkeypatch.setattr(deliverability, '_txt_records', lambda name: None)
    result = deliverability.check_domain('acme.test')
    assert result['spf_status'] == 'error'
    assert result['dmarc_status'] == 'error'
    assert result['status'] == 'error'


@pytest.mark.django_db
def test_invalid_domain_short_circuits():
    result = deliverability.check_domain('not-a-domain')
    assert result['status'] == 'error'
    assert result['fingerprint'] == ''


def test_fingerprint_changes_with_records():
    base = {
        'spf_status': 'pass', 'spf_record': 'v=spf1 -all',
        'dmarc_status': 'pass', 'dmarc_policy': 'reject', 'dmarc_record': 'v=DMARC1; p=reject',
        'dkim_status': 'found', 'dkim_selectors': ['google'],
    }
    changed = {**base, 'dmarc_policy': 'none', 'dmarc_record': 'v=DMARC1; p=none'}
    assert deliverability._fingerprint(base) != deliverability._fingerprint(changed)


# --------------------------------------------------------------------------
# sending_domains
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_sending_domains_dedupes_and_lowercases(user_a):
    _account(user_a, 'alice@Acme.TEST')
    _account(user_a, 'bob@acme.test')
    _account(user_a, 'carol@other.test')
    assert deliverability.sending_domains(user_a) == ['acme.test', 'other.test']


@pytest.mark.django_db
def test_sending_domains_ignores_disconnected(user_a):
    acc = _account(user_a, 'x@acme.test')
    acc.is_connected = False
    acc.save()
    assert deliverability.sending_domains(user_a) == []


# --------------------------------------------------------------------------
# Monitor runner + drift
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_monitor_persists_and_alerts_on_first_failing(user_a, monkeypatch):
    _account(user_a, 'x@acme.test')
    monkeypatch.setattr(deliverability, 'check_domain', lambda d: {
        'domain': d, 'status': 'failing',
        'spf_status': 'missing', 'spf_record': '',
        'dkim_status': 'unknown', 'dkim_selectors': [],
        'dmarc_status': 'missing', 'dmarc_policy': '', 'dmarc_record': '',
        'issues': ['No SPF record found.'], 'fingerprint': 'fp1',
    })
    rows = deliverability.run_deliverability_monitor(user_a)
    assert len(rows) == 1
    row = DomainDeliverability.objects.get(user=user_a, domain='acme.test')
    assert row.status == 'failing'
    assert row.has_alert is True
    assert 'acme.test' in row.alert_message


@pytest.mark.django_db
def test_monitor_no_alert_when_healthy_and_stable(user_a, monkeypatch):
    _account(user_a, 'x@acme.test')
    healthy = {
        'domain': 'acme.test', 'status': 'healthy',
        'spf_status': 'pass', 'spf_record': 'v=spf1 -all',
        'dkim_status': 'found', 'dkim_selectors': ['google'],
        'dmarc_status': 'pass', 'dmarc_policy': 'reject', 'dmarc_record': 'v=DMARC1; p=reject',
        'issues': [], 'fingerprint': 'fp-stable',
    }
    monkeypatch.setattr(deliverability, 'check_domain', lambda d: healthy)
    deliverability.run_deliverability_monitor(user_a)  # baseline
    deliverability.run_deliverability_monitor(user_a)  # unchanged
    row = DomainDeliverability.objects.get(user=user_a, domain='acme.test')
    assert row.has_alert is False


@pytest.mark.django_db
def test_monitor_alerts_on_drift(user_a, monkeypatch):
    _account(user_a, 'x@acme.test')
    healthy = {
        'domain': 'acme.test', 'status': 'healthy',
        'spf_status': 'pass', 'spf_record': 'v=spf1 -all',
        'dkim_status': 'found', 'dkim_selectors': ['google'],
        'dmarc_status': 'pass', 'dmarc_policy': 'reject', 'dmarc_record': 'v=DMARC1; p=reject',
        'issues': [], 'fingerprint': 'fp-healthy',
    }
    monkeypatch.setattr(deliverability, 'check_domain', lambda d: healthy)
    deliverability.run_deliverability_monitor(user_a)
    row = DomainDeliverability.objects.get(user=user_a, domain='acme.test')
    assert row.has_alert is False
    baseline_changed = row.last_changed_at

    # DMARC policy reverts to none: fingerprint moves, drift must fire.
    drifted = {**healthy, 'status': 'at_risk', 'dmarc_policy': 'none',
               'dmarc_record': 'v=DMARC1; p=none', 'fingerprint': 'fp-drifted',
               'issues': ['DMARC policy is p=none.']}
    monkeypatch.setattr(deliverability, 'check_domain', lambda d: drifted)
    deliverability.run_deliverability_monitor(user_a)

    row.refresh_from_db()
    assert row.has_alert is True
    assert 'DMARC' in row.alert_message
    assert row.last_changed_at != baseline_changed


@pytest.mark.django_db
def test_monitor_is_tenant_scoped(user_a, user_b, monkeypatch):
    _account(user_b, 'x@theirs.test')
    monkeypatch.setattr(deliverability, 'check_domain', lambda d: {
        'domain': d, 'status': 'healthy', 'spf_status': 'pass', 'spf_record': '',
        'dkim_status': 'found', 'dkim_selectors': [], 'dmarc_status': 'pass',
        'dmarc_policy': 'reject', 'dmarc_record': '', 'issues': [], 'fingerprint': 'f',
    })
    deliverability.run_deliverability_monitor(user_a)
    assert DomainDeliverability.objects.filter(user=user_a).count() == 0


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_deliverability_get_includes_domains(auth_a, user_a):
    DomainDeliverability.objects.create(
        user=user_a, domain='acme.test', status='failing', spf_status='missing',
        dmarc_status='missing', has_alert=True, alert_message='acme.test authentication is failing',
    )
    resp = auth_a.get('/api/integrations/deliverability/?period=30d')
    assert resp.status_code == 200
    data = resp.json()
    assert any(d['domain'] == 'acme.test' for d in data['domains'])
    assert len(data['domain_alerts']) == 1
    assert data['summary']['domain_alerts'] == 1


@pytest.mark.django_db
def test_deliverability_post_runs_check(auth_a, user_a, monkeypatch):
    _account(user_a, 'x@acme.test')
    monkeypatch.setattr(deliverability, 'check_domain', lambda d: {
        'domain': d, 'status': 'healthy', 'spf_status': 'pass', 'spf_record': 'v=spf1 -all',
        'dkim_status': 'found', 'dkim_selectors': ['google'], 'dmarc_status': 'pass',
        'dmarc_policy': 'reject', 'dmarc_record': 'v=DMARC1; p=reject', 'issues': [],
        'fingerprint': 'fp',
    })
    resp = auth_a.post('/api/integrations/deliverability/')
    assert resp.status_code == 200
    data = resp.json()
    assert data['checked'] == 1
    assert data['domains'][0]['domain'] == 'acme.test'
    assert data['domains'][0]['status'] == 'healthy'


@pytest.mark.django_db
def test_deliverability_requires_auth(api):
    assert api.get('/api/integrations/deliverability/').status_code in (401, 403)
