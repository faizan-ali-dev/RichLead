"""Feature 1: ICP fit scoring and queue ordering."""
import pytest

from ai_engine.business import BusinessProfile
from ai_engine.scoring import NEUTRAL_SCORE, apply_icp_score, compute_icp_score, rescore_user_leads
from leads.models import Lead, ScoreBreakdown


def _profile(user, **kw):
    defaults = dict(what_you_do='x', problem_you_solve='y')
    defaults.update(kw)
    return BusinessProfile.objects.create(user=user, **defaults)


def _lead(user, **kw):
    defaults = dict(name='L', company='C', niche='n', email=f"{kw.get('email','l')}@x.test", status='pending')
    defaults.update(kw)
    defaults['email'] = f"{defaults.pop('tag', 'l')}@x.test" if 'tag' in kw else defaults['email']
    return Lead.objects.create(user=user, **defaults)


# --------------------------------------------------------------------------
# Pure scoring
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_no_icp_yields_neutral_score(user_a):
    profile = _profile(user_a)
    lead = Lead(user=user_a, title='CEO', industry='SaaS')
    score, breakdown = compute_icp_score(lead, profile)
    assert score == NEUTRAL_SCORE
    assert breakdown == []


@pytest.mark.django_db
def test_perfect_match_scores_high(user_a):
    profile = _profile(
        user_a,
        icp_titles=['head of sales'], icp_industries=['saas'],
        icp_locations=['united states'], icp_employee_min=20, icp_employee_max=200,
    )
    lead = Lead(
        user=user_a, title='Head of Sales', industry='SaaS',
        location='United States', employee_count=80,
    )
    score, breakdown = compute_icp_score(lead, profile)
    assert score >= 95
    assert {b['factor'] for b in breakdown} == {'title', 'industry', 'company_size', 'location'}


@pytest.mark.django_db
def test_wrong_title_scores_low(user_a):
    profile = _profile(user_a, icp_titles=['head of sales'])
    lead = Lead(user=user_a, title='Junior Developer')
    score, _ = compute_icp_score(lead, profile)
    assert score < 20


@pytest.mark.django_db
def test_partial_title_match_gets_partial_credit(user_a):
    profile = _profile(user_a, icp_titles=['sales'])
    lead = Lead(user=user_a, title='VP of Sales Operations')
    score, _ = compute_icp_score(lead, profile)
    assert 40 <= score <= 80  # substring hit, not exact


@pytest.mark.django_db
def test_company_size_near_miss_gets_partial_credit(user_a):
    profile = _profile(user_a, icp_employee_min=50, icp_employee_max=500)
    near = compute_icp_score(Lead(user=user_a, employee_count=45), profile)[0]
    far = compute_icp_score(Lead(user=user_a, employee_count=3), profile)[0]
    assert near > far


@pytest.mark.django_db
def test_funding_requirement(user_a):
    profile = _profile(user_a, icp_requires_funding=True)
    funded = compute_icp_score(Lead(user=user_a, funding_amount='$10M'), profile)[0]
    unfunded = compute_icp_score(Lead(user=user_a), profile)[0]
    assert funded > unfunded


@pytest.mark.django_db
def test_sparse_enrichment_scores_on_known_factors_only(user_a):
    """A lead with only a title still scores against the title criterion."""
    profile = _profile(user_a, icp_titles=['cto'], icp_industries=['fintech'], icp_employee_min=100)
    lead = Lead(user=user_a, title='CTO')  # no industry, no employee_count
    score, breakdown = compute_icp_score(lead, profile)
    assert [b['factor'] for b in breakdown] == ['title']
    assert score >= 95  # full marks on the only scorable factor


# --------------------------------------------------------------------------
# Persistence + signal
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_apply_persists_score_and_breakdown(user_a):
    profile = _profile(user_a, icp_titles=['ceo'], icp_industries=['saas'])
    lead = Lead.objects.create(user=user_a, name='L', company='C', niche='SaaS',
                               email='apply@x.test', title='CEO', industry='SaaS', status='reached')

    score = apply_icp_score(lead, profile)
    lead.refresh_from_db()
    assert lead.icp_score == score >= 95
    assert ScoreBreakdown.objects.filter(lead=lead).count() == 2


@pytest.mark.django_db
def test_lead_is_scored_automatically_on_create(user_a):
    _profile(user_a, icp_titles=['head of sales'], icp_industries=['saas'])
    lead = Lead.objects.create(user=user_a, name='Carol', company='Globex', niche='SaaS',
                               email='auto@x.test', title='Head of Sales', industry='SaaS')
    lead.refresh_from_db()
    assert lead.icp_score >= 95


@pytest.mark.django_db
def test_scoring_signal_does_not_recurse(user_a):
    """apply_icp_score saves icp_score, which must not re-trigger scoring forever."""
    _profile(user_a, icp_titles=['ceo'])
    # If this returns, there is no infinite recursion.
    lead = Lead.objects.create(user=user_a, name='L', company='C', niche='n',
                               email='norecurse@x.test', title='CEO')
    assert lead.pk is not None


@pytest.mark.django_db
def test_only_pending_leads_are_auto_scored(user_a):
    _profile(user_a, icp_titles=['ceo'])
    lead = Lead.objects.create(user=user_a, name='L', company='C', niche='n',
                               email='sent@x.test', title='Nobody', status='reached')
    lead.refresh_from_db()
    assert lead.icp_score == 0  # untouched; not pending


@pytest.mark.django_db
def test_rescore_updates_all_pending_leads(user_a):
    profile = _profile(user_a)  # no ICP yet -> neutral
    for i in range(3):
        Lead.objects.create(user=user_a, name=f'L{i}', company='C', niche='SaaS',
                            email=f'r{i}@x.test', title='Head of Sales', industry='SaaS')

    profile.icp_titles = ['head of sales']
    profile.icp_industries = ['saas']
    profile.save()

    updated = rescore_user_leads(user_a, profile)
    assert updated == 3
    assert all(l.icp_score >= 95 for l in Lead.objects.filter(user=user_a))


# --------------------------------------------------------------------------
# API + queue ordering
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_icp_fields_round_trip(auth_a):
    resp = auth_a.patch('/api/ai/business-profile/', {
        'icp_titles': ['Head of Sales', 'SDR Manager'],
        'icp_industries': ['SaaS'],
        'icp_employee_min': 20,
        'icp_employee_max': 200,
    }, format='json')
    assert resp.status_code == 200
    data = resp.json()
    assert data['icp_titles'] == ['head of sales', 'sdr manager']  # normalised
    assert data['has_icp'] is True


@pytest.mark.django_db
def test_employee_max_below_min_is_rejected(auth_a):
    resp = auth_a.patch('/api/ai/business-profile/',
                        {'icp_employee_min': 200, 'icp_employee_max': 50}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_changing_icp_rescores_pending_leads(auth_a, user_a):
    for i in range(2):
        Lead.objects.create(user=user_a, name=f'L{i}', company='C', niche='SaaS',
                            email=f'q{i}@x.test', title='Head of Sales', industry='SaaS')

    resp = auth_a.patch('/api/ai/business-profile/', {
        'icp_titles': ['head of sales'], 'icp_industries': ['saas'],
    }, format='json')
    assert resp.status_code == 200
    assert resp.json()['rescored_leads'] == 2
    assert all(l.icp_score >= 95 for l in Lead.objects.filter(user=user_a))


@pytest.mark.django_db
def test_draft_queue_orders_by_icp_fit(user_a, monkeypatch):
    """Best-fit leads must be drafted first."""
    from ai_engine import providers, services
    from integrations.models import APIIntegration

    integ = APIIntegration(user=user_a, provider='anthropic', model='claude-opus-5', is_primary=True)
    integ.set_api_key('sk-test')
    integ.save()
    _profile(user_a, icp_titles=['head of sales'])

    Lead.objects.create(user=user_a, name='Bad', company='C', niche='n',
                        email='bad@x.test', title='Intern')
    Lead.objects.create(user=user_a, name='Good', company='C', niche='n',
                        email='good@x.test', title='Head of Sales')

    order = []

    def fake_generate(provider, api_key, model, **kw):
        import json
        # Capture which lead is being drafted by its company context in the prompt
        order.append(kw['user_prompt'])
        return json.dumps({'pain_point': 'p', 'subject': 's', 'body': 'A draft. Worth a look?'})

    monkeypatch.setattr(providers, 'generate', fake_generate)
    services.draft_pending_leads(user_a, limit=1)

    # Only one draft allowed; it must be the high-fit lead.
    assert 'Head of Sales' in order[0]
