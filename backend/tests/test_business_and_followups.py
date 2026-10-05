"""Business profile, follow-up cadence, and the pre-drafted review queue."""
import pytest

from ai_engine import providers
from ai_engine.models import BusinessProfile, FollowUpSettings
from ai_engine.services import draft_pending_leads, generate_outreach_message, needs_draft
from integrations.models import APIIntegration
from leads.models import AIResearch, Lead


def _llm(user):
    integration = APIIntegration(user=user, provider='anthropic',
                                 model='claude-opus-5', is_primary=True)
    integration.set_api_key('sk-test')
    integration.save()
    return integration


def _json_draft(subject='a subject', body='A short note. Worth a look?'):
    import json
    return json.dumps({'pain_point': 'Manual list building.', 'subject': subject, 'body': body})


# --------------------------------------------------------------------------
# Business profile
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_profile_is_created_on_first_access(auth_a, user_a):
    resp = auth_a.get('/api/ai/business-profile/')
    assert resp.status_code == 200
    assert resp.json()['is_complete'] is False
    assert BusinessProfile.objects.filter(user=user_a).exists()


@pytest.mark.django_db
def test_profile_round_trip(auth_a):
    resp = auth_a.patch('/api/ai/business-profile/', {
        'company_name': 'Acme',
        'what_you_do': 'We cut list building time for SDR teams.',
        'problem_you_solve': 'SDRs lose an hour a day to manual research.',
    }, format='json')

    assert resp.status_code == 200
    assert resp.json()['is_complete'] is True
    assert auth_a.get('/api/ai/business-profile/').json()['company_name'] == 'Acme'


@pytest.mark.django_db
def test_profile_is_tenant_scoped(auth_a, auth_b):
    auth_a.patch('/api/ai/business-profile/', {'company_name': 'Acme'}, format='json')
    assert auth_b.get('/api/ai/business-profile/').json()['company_name'] == ''


@pytest.mark.django_db
def test_profile_requires_authentication(api):
    assert api.get('/api/ai/business-profile/').status_code in (401, 403)


@pytest.mark.django_db
def test_empty_profile_contributes_nothing_to_the_prompt(user_a):
    profile = BusinessProfile.objects.create(user=user_a)
    assert profile.as_prompt_block() == ''


@pytest.mark.django_db
def test_profile_renders_only_filled_fields(user_a):
    profile = BusinessProfile.objects.create(
        user=user_a, company_name='Acme',
        what_you_do='We cut list building time.',
    )
    block = profile.as_prompt_block()

    assert 'Company: Acme' in block
    assert 'What we do: We cut list building time.' in block
    assert 'Customer story' not in block, 'blank fields must not appear as empty labels'


@pytest.mark.django_db
def test_never_claim_is_rendered_as_a_prohibition(user_a):
    profile = BusinessProfile.objects.create(
        user=user_a, what_you_do='x', never_claim='SOC 2 certification',
    )
    block = profile.as_prompt_block()

    assert 'NEVER CLAIM' in block
    assert 'SOC 2 certification' in block


@pytest.mark.django_db
def test_profile_forbids_inventing_facts(user_a):
    profile = BusinessProfile.objects.create(user=user_a, what_you_do='x')
    assert 'Do not invent' in profile.as_prompt_block()


# --------------------------------------------------------------------------
# Business profile reaches the model
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_business_profile_is_sent_to_the_model(user_a, lead_a, monkeypatch):
    _llm(user_a)
    BusinessProfile.objects.create(
        user=user_a,
        company_name='Acme',
        what_you_do='We cut list building time for SDR teams.',
        problem_you_solve='SDRs lose an hour a day to manual research.',
        differentiator='Sets up in ten minutes, no data team needed.',
        never_claim='SOC 2 certification',
    )

    captured = {}
    monkeypatch.setattr(providers, 'generate',
                        lambda *a, **k: (captured.update(k), _json_draft())[1])

    generate_outreach_message(lead_a.id, user_a)

    system = captured['system_prompt']
    assert 'Company: Acme' in system
    assert 'We cut list building time for SDR teams.' in system
    assert 'Sets up in ten minutes' in system
    assert 'SOC 2 certification' in system
    # The guardrails must still survive alongside it.
    assert 'Never use em dashes' in system


@pytest.mark.django_db
def test_generation_works_without_a_business_profile(user_a, lead_a, monkeypatch):
    _llm(user_a)
    monkeypatch.setattr(providers, 'generate', lambda *a, **k: _json_draft())

    assert generate_outreach_message(lead_a.id, user_a)['success'] is True


# --------------------------------------------------------------------------
# Follow-up settings
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_followups_have_sensible_defaults(auth_a):
    data = auth_a.get('/api/ai/followup-settings/').json()
    assert data['total_follow_ups'] == 2
    assert data['days_between'] == 4
    assert data['total_touches'] == 3
    assert data['stop_on_reply'] is True


@pytest.mark.django_db
def test_followups_round_trip(auth_a):
    resp = auth_a.patch('/api/ai/followup-settings/',
                        {'total_follow_ups': 3, 'days_between': 5}, format='json')
    assert resp.status_code == 200
    assert resp.json()['total_touches'] == 4


@pytest.mark.django_db
def test_too_many_followups_is_rejected(auth_a):
    resp = auth_a.patch('/api/ai/followup-settings/', {'total_follow_ups': 12}, format='json')
    assert resp.status_code == 400
    assert 'complaints' in str(resp.json()).lower()


@pytest.mark.django_db
def test_too_short_an_interval_is_rejected(auth_a):
    resp = auth_a.patch('/api/ai/followup-settings/', {'days_between': 1}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_zero_followups_means_send_once(auth_a):
    resp = auth_a.patch('/api/ai/followup-settings/', {'total_follow_ups': 0}, format='json')
    assert resp.status_code == 200
    assert resp.json()['total_touches'] == 1


@pytest.mark.django_db
def test_followups_are_tenant_scoped(auth_a, auth_b):
    auth_a.patch('/api/ai/followup-settings/', {'total_follow_ups': 4}, format='json')
    assert auth_b.get('/api/ai/followup-settings/').json()['total_follow_ups'] == 2


@pytest.mark.django_db
def test_model_clamps_out_of_range_values(user_a):
    settings_obj = FollowUpSettings.objects.create(
        user=user_a, total_follow_ups=99, days_between=0,
    )
    settings_obj.refresh_from_db()
    assert settings_obj.total_follow_ups == FollowUpSettings.MAX_FOLLOW_UPS
    assert settings_obj.days_between == FollowUpSettings.MIN_DAYS_BETWEEN


# --------------------------------------------------------------------------
# Pre-drafted review queue
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_needs_draft_detects_missing_and_blank(user_a, lead_a):
    assert needs_draft(lead_a) is True

    AIResearch.objects.create(lead=lead_a, summary='s', generated_message='   ')
    lead_a.refresh_from_db()
    assert needs_draft(lead_a) is True

    lead_a.research.generated_message = 'A real draft.'
    lead_a.research.save()
    lead_a.refresh_from_db()
    assert needs_draft(lead_a) is False


@pytest.mark.django_db
def test_queue_drafts_every_pending_lead(user_a, monkeypatch):
    _llm(user_a)
    for i in range(3):
        Lead.objects.create(user=user_a, name=f'L{i}', company='C', niche='n',
                            email=f'q{i}@x.test', status='pending')

    monkeypatch.setattr(providers, 'generate', lambda *a, **k: _json_draft())

    result = draft_pending_leads(user_a)

    assert result['success'] is True
    assert result['drafted'] == 3
    assert AIResearch.objects.filter(lead__user=user_a).count() == 3


@pytest.mark.django_db
def test_queue_skips_leads_that_already_have_a_draft(user_a, lead_a, monkeypatch):
    _llm(user_a)
    AIResearch.objects.create(lead=lead_a, summary='s', generated_message='Already written.')

    calls = []
    monkeypatch.setattr(providers, 'generate',
                        lambda *a, **k: (calls.append(1), _json_draft())[1])

    result = draft_pending_leads(user_a)

    assert calls == []
    assert result['drafted'] == 0
    assert 'already has a draft' in result['message']


@pytest.mark.django_db
def test_queue_only_drafts_pending_leads(user_a, monkeypatch):
    _llm(user_a)
    Lead.objects.create(user=user_a, name='Sent', company='C', niche='n',
                        email='sent@x.test', status='reached')
    Lead.objects.create(user=user_a, name='Blocked', company='C', niche='n',
                        email='blocked@x.test', status='blacklisted')

    monkeypatch.setattr(providers, 'generate', lambda *a, **k: _json_draft())
    assert draft_pending_leads(user_a)['drafted'] == 0


@pytest.mark.django_db
def test_queue_is_capped(user_a, monkeypatch):
    """Each draft is a paid completion, so a big import must not run away."""
    _llm(user_a)
    for i in range(8):
        Lead.objects.create(user=user_a, name=f'L{i}', company='C', niche='n',
                            email=f'cap{i}@x.test', status='pending')

    monkeypatch.setattr(providers, 'generate', lambda *a, **k: _json_draft())

    result = draft_pending_leads(user_a, limit=3)
    assert result['drafted'] == 3
    assert result['remaining'] == 5


@pytest.mark.django_db
def test_queue_reports_setup_needed_without_a_provider(user_a):
    Lead.objects.create(user=user_a, name='L', company='C', niche='n',
                        email='nolllm@x.test', status='pending')

    result = draft_pending_leads(user_a)
    assert result['success'] is False
    assert result['needs_setup'] is True


@pytest.mark.django_db
def test_queue_stops_after_repeated_provider_failures(user_a, monkeypatch):
    """A bad key fails identically for every lead; don't burn the whole batch."""
    _llm(user_a)
    for i in range(10):
        Lead.objects.create(user=user_a, name=f'L{i}', company='C', niche='n',
                            email=f'fail{i}@x.test', status='pending')

    calls = []

    def boom(*a, **k):
        calls.append(1)
        raise providers.ProviderError('Invalid API key.')

    monkeypatch.setattr(providers, 'generate', boom)
    result = draft_pending_leads(user_a)

    assert result['drafted'] == 0
    assert len(calls) <= 3, 'should stop early rather than retry every lead'


@pytest.mark.django_db
def test_queue_endpoint(auth_a, user_a, monkeypatch):
    _llm(user_a)
    Lead.objects.create(user=user_a, name='L', company='C', niche='n',
                        email='ep@x.test', status='pending')
    monkeypatch.setattr(providers, 'generate', lambda *a, **k: _json_draft())

    resp = auth_a.post('/api/ai/draft-queue/', {}, format='json')
    assert resp.status_code == 200
    # The endpoint runs the draft batch as a background job and returns its
    # envelope; under eager test settings it comes back already succeeded.
    assert resp.json()['result']['drafted'] == 1


@pytest.mark.django_db
def test_queue_is_tenant_scoped(auth_a, user_a, user_b, monkeypatch):
    _llm(user_a)
    Lead.objects.create(user=user_b, name='Theirs', company='C', niche='n',
                        email='theirs@x.test', status='pending')

    monkeypatch.setattr(providers, 'generate', lambda *a, **k: _json_draft())
    assert auth_a.post('/api/ai/draft-queue/', {}, format='json').json()['result']['drafted'] == 0


@pytest.mark.django_db
def test_drafted_leads_expose_subject_and_body_for_approval(auth_a, user_a, monkeypatch):
    """The reviewer should open the queue to finished copy, not a Generate button."""
    _llm(user_a)
    lead = Lead.objects.create(user=user_a, name='L', company='Globex', niche='SaaS',
                               email='ready@x.test', status='pending')
    monkeypatch.setattr(providers, 'generate',
                        lambda *a, **k: _json_draft('list building', 'A ready draft. Worth a look?'))

    auth_a.post('/api/ai/draft-queue/', {}, format='json')

    body = auth_a.get('/api/leads/').json()
    rows = body['results'] if isinstance(body, dict) else body
    row = next(r for r in rows if r['id'] == lead.id)

    assert row['message'] == 'A ready draft. Worth a look?'
