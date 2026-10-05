"""Feature 4: A/B subject-line testing."""
import pytest
from django.utils import timezone

from ai_engine import providers, services
from ai_engine.experiments import (
    SubjectExperiment, assign_variant, evaluate_experiment, experiment_results,
)
from integrations.models import APIIntegration
from leads.models import Lead


def _llm(user):
    integ = APIIntegration(user=user, provider='anthropic', model='claude-opus-5', is_primary=True)
    integ.set_api_key('sk-test')
    integ.save()


def _experiment(user, status='running'):
    return SubjectExperiment.objects.create(user=user, status=status)


def _lead(user, tag, **kw):
    return Lead.objects.create(user=user, name='L', company='C', niche='n',
                               email=f'{tag}@x.test', **kw)


# --------------------------------------------------------------------------
# Assignment
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_no_experiment_assigns_nothing(user_a, lead_a):
    variant, instruction = assign_variant(user_a, lead_a)
    assert variant is None and instruction == ''


@pytest.mark.django_db
def test_off_experiment_assigns_nothing(user_a, lead_a):
    _experiment(user_a, status='off')
    assert assign_variant(user_a, lead_a)[0] is None


@pytest.mark.django_db
def test_running_experiment_assigns_a_variant(user_a, lead_a):
    exp = _experiment(user_a)
    variant, instruction = assign_variant(user_a, lead_a, exp)
    assert variant in ('a', 'b')
    assert instruction == exp.instruction_for(variant)
    lead_a.refresh_from_db()
    assert lead_a.subject_variant == variant


@pytest.mark.django_db
def test_assignment_is_sticky(user_a, lead_a):
    exp = _experiment(user_a)
    first = assign_variant(user_a, lead_a, exp)[0]
    second = assign_variant(user_a, lead_a, exp)[0]
    assert first == second  # regenerating must not re-roll the arm


@pytest.mark.django_db
def test_decided_experiment_uses_the_winner(user_a, lead_a):
    exp = SubjectExperiment.objects.create(user=user_a, status='decided', winner='b')
    variant, instruction = assign_variant(user_a, lead_a, exp)
    assert variant == 'b'
    assert instruction == exp.variant_b_instruction


@pytest.mark.django_db
def test_random_assignment_covers_both_arms(user_a):
    exp = _experiment(user_a)
    seen = set()
    for i in range(40):
        lead = _lead(user_a, f'rand{i}')
        seen.add(assign_variant(user_a, lead, exp)[0])
    assert seen == {'a', 'b'}


# --------------------------------------------------------------------------
# Results + decision
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_results_aggregate_sent_and_replied_per_variant(user_a):
    now = timezone.now()
    _lead(user_a, 's1', subject_variant='a', first_sent_at=now, replied_at=now)
    _lead(user_a, 's2', subject_variant='a', first_sent_at=now)
    _lead(user_a, 's3', subject_variant='b', first_sent_at=now)

    stats = experiment_results(user_a)
    assert stats['a'] == {'sent': 2, 'replied': 1, 'reply_rate': 0.5}
    assert stats['b'] == {'sent': 1, 'replied': 0, 'reply_rate': 0.0}


@pytest.mark.django_db
def test_no_decision_below_minimum_sample(user_a):
    exp = _experiment(user_a)
    now = timezone.now()
    for i in range(5):
        _lead(user_a, f'a{i}', subject_variant='a', first_sent_at=now, replied_at=now)
        _lead(user_a, f'b{i}', subject_variant='b', first_sent_at=now)
    assert evaluate_experiment(user_a, exp) == ''
    exp.refresh_from_db()
    assert exp.status == 'running'


@pytest.mark.django_db
def test_clear_winner_is_promoted(user_a):
    exp = _experiment(user_a)
    now = timezone.now()
    # Variant A: 40 sent, 20 replied (50%). Variant B: 40 sent, 2 replied (5%).
    for i in range(40):
        _lead(user_a, f'a{i}', subject_variant='a', first_sent_at=now,
              replied_at=now if i < 20 else None)
        _lead(user_a, f'b{i}', subject_variant='b', first_sent_at=now,
              replied_at=now if i < 2 else None)

    winner = evaluate_experiment(user_a, exp)
    assert winner == 'a'
    exp.refresh_from_db()
    assert exp.status == 'decided'
    assert exp.decided_at is not None


@pytest.mark.django_db
def test_no_decision_when_rates_are_close(user_a):
    exp = _experiment(user_a)
    now = timezone.now()
    # Both ~25%: no meaningful difference despite large sample.
    for i in range(80):
        _lead(user_a, f'a{i}', subject_variant='a', first_sent_at=now,
              replied_at=now if i < 20 else None)
        _lead(user_a, f'b{i}', subject_variant='b', first_sent_at=now,
              replied_at=now if i < 21 else None)
    assert evaluate_experiment(user_a, exp) == ''


# --------------------------------------------------------------------------
# Generation integration
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_generation_injects_the_variant_subject_instruction(user_a, lead_a, monkeypatch):
    _llm(user_a)
    exp = SubjectExperiment.objects.create(
        user=user_a, status='decided', winner='a',
        variant_a_instruction='Write the subject as a question.',
    )

    captured = {}

    def fake_generate(provider, api_key, model, **kw):
        import json
        captured.update(kw)
        return json.dumps({'pain_point': 'p', 'subject': 's', 'body': 'A draft. Worth a look?'})

    monkeypatch.setattr(providers, 'generate', fake_generate)
    services.generate_outreach_message(lead_a.id, user_a)

    assert 'Write the subject as a question.' in captured['system_prompt']
    lead_a.refresh_from_db()
    assert lead_a.subject_variant == 'a'


@pytest.mark.django_db
def test_generation_without_experiment_has_no_subject_style(user_a, lead_a, monkeypatch):
    _llm(user_a)
    captured = {}
    monkeypatch.setattr(providers, 'generate',
                        lambda *a, **k: (captured.update(k),
                                         '{"pain_point":"p","subject":"s","body":"b. Worth a look?"}')[1])
    services.generate_outreach_message(lead_a.id, user_a)
    assert 'SUBJECT STYLE FOR THIS EMAIL' not in captured['system_prompt']


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_experiment_endpoint_round_trip(auth_a):
    resp = auth_a.patch('/api/ai/subject-experiment/', {
        'status': 'running',
        'variant_a_label': 'Question', 'variant_a_instruction': 'Ask a question.',
        'variant_b_label': 'Statement', 'variant_b_instruction': 'State the problem.',
    }, format='json')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'running'
    assert 'results' in resp.json()


@pytest.mark.django_db
def test_experiment_status_validation(auth_a):
    resp = auth_a.patch('/api/ai/subject-experiment/', {'status': 'decided'}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_experiment_is_tenant_scoped(auth_a, auth_b):
    auth_a.patch('/api/ai/subject-experiment/', {'status': 'running'}, format='json')
    assert auth_b.get('/api/ai/subject-experiment/').json()['status'] == 'off'


@pytest.mark.django_db
def test_rerunning_clears_prior_winner(auth_a, user_a):
    SubjectExperiment.objects.create(user=user_a, status='decided', winner='a',
                                     decided_at=timezone.now())
    resp = auth_a.patch('/api/ai/subject-experiment/', {'status': 'running'}, format='json')
    assert resp.json()['winner'] == ''
    assert resp.json()['decided_at'] is None
