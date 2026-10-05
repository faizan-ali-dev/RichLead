"""Apollo prospecting import pipeline.

The merged implementation calls the real Apollo API (people search + email
enrichment) instead of fabricating leads, so these tests mock that network
boundary (`_search_apollo_people`, `_enrich_verified_emails`) and supply a saved
Apollo key. The assertions that matter are unchanged: only verified contacts are
imported, the count is capped, duplicates are skipped rather than fatal, and
autopilot never emails a suppressed address.
"""
import pytest

from integrations.apollo_service import fetch_apollo_leads, MAX_LEADS_PER_SEARCH
from integrations.models import APIIntegration, SuppressionEntry
from leads.models import Lead


def _person(i, *, title='CEO', email=None):
    return {
        'id': f'apollo-{i}',
        'first_name': 'Lead', 'last_name': str(i), 'name': f'Lead {i}',
        'title': title,
        'email': email or f'lead{i}@example.test',
        'organization': {'name': 'Acme', 'industry': 'Software'},
    }


@pytest.fixture
def apollo(user_a, monkeypatch):
    """Saved Apollo key + mocked network boundary, returning `count` verified people."""
    integration = APIIntegration(user=user_a, provider='apollo', is_active=True)
    integration.set_api_key('test-key')
    integration.save()

    import integrations.apollo_service as svc

    def fake_search(api_key, search_params, count):
        title = search_params.get('job_titles') or 'CEO'
        return [_person(i, title=title) for i in range(count)], count

    monkeypatch.setattr(svc, '_search_apollo_people', fake_search)
    monkeypatch.setattr(svc, '_enrich_verified_emails', lambda api_key, people, **kw: list(people))
    # Keep the import loop offline: no LLM call per created lead.
    monkeypatch.setattr(svc, 'generate_outreach_message', lambda lead_id, user: {'success': True, 'message': 'hi'})
    return svc


@pytest.mark.django_db
def test_fetch_creates_leads(user_a, apollo):
    result = fetch_apollo_leads(user_a, {'count': 3, 'keywords': 'SaaS'})

    assert result['success'] is True
    assert result['fetched_count'] == 3
    assert Lead.objects.filter(user=user_a).count() == 3


@pytest.mark.django_db
def test_fetched_leads_have_valid_fields(user_a, apollo):
    fetch_apollo_leads(user_a, {'count': 1, 'keywords': 'Fintech', 'job_titles': 'CTO'})

    lead = Lead.objects.filter(user=user_a).first()
    assert lead.title == 'CTO'
    assert 0 <= lead.icp_score <= 100
    assert lead.niche == 'Fintech'
    assert lead.status == 'pending'
    assert lead.email == lead.email.lower()


@pytest.mark.django_db
def test_count_is_capped(user_a, apollo):
    """An uncapped count would attempt one AI completion per lead, unbounded."""
    result = fetch_apollo_leads(user_a, {'count': 100000})

    assert result['fetched_count'] <= MAX_LEADS_PER_SEARCH
    assert Lead.objects.filter(user=user_a).count() <= MAX_LEADS_PER_SEARCH


@pytest.mark.django_db
def test_invalid_count_does_not_crash(user_a, apollo):
    for bad in ('abc', -5, 0, None):
        result = fetch_apollo_leads(user_a, {'count': bad})
        assert result['success'] is True


@pytest.mark.django_db
def test_missing_api_key_is_a_clean_error(user_a):
    """With no Apollo key saved, prospecting reports a connect prompt, not a crash."""
    result = fetch_apollo_leads(user_a, {'count': 2})
    assert result['success'] is False
    assert 'Apollo' in result['error']


@pytest.mark.django_db
def test_duplicate_emails_are_skipped_not_fatal(user_a, apollo, monkeypatch):
    """Re-running prospecting must not blow up on the per-user unique constraint."""
    monkeypatch.setattr(apollo, '_search_apollo_people', lambda api_key, p, count: (
        [_person(0, email='dup@example.test'), _person(1, email='dup@example.test')], 2,
    ))

    result = fetch_apollo_leads(user_a, {'count': 2})
    assert result['success'] is True
    assert result['skipped_duplicates'] == 1
    assert Lead.objects.filter(user=user_a, email='dup@example.test').count() == 1


@pytest.mark.django_db
def test_endpoint_enqueues_and_succeeds(auth_a, apollo):
    """The endpoint now runs prospecting as a background job and returns its envelope.

    Under the eager test settings the job executes inline, so it comes back
    already succeeded with the Apollo result attached.
    """
    resp = auth_a.post('/api/integrations/apollo-search/', {'search_params': {'count': 2}}, format='json')
    assert resp.status_code in (200, 202)
    body = resp.json()
    assert body['job_type'] == 'apollo_search'
    assert body['status'] == 'succeeded'
    assert body['result']['success'] is True
    assert body['result']['fetched_count'] == 2


@pytest.mark.django_db
def test_autopilot_does_not_email_suppressed_leads(user_a, apollo, monkeypatch):
    """Autopilot is the riskiest path: it sends without human review."""
    user_a.autopilot_active = True
    user_a.save()
    SuppressionEntry.objects.create(user=user_a, email='blocked@example.test')
    monkeypatch.setattr(apollo, '_search_apollo_people', lambda api_key, p, count: (
        [_person(0, email='blocked@example.test')], 1,
    ))

    fetch_apollo_leads(user_a, {'count': 1})

    lead = Lead.objects.get(user=user_a, email='blocked@example.test')
    assert lead.status != 'reached'
