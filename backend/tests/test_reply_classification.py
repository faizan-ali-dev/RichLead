"""Feature 3: reply intent classification and auto-actions."""
import pytest
from django.utils import timezone

from ai_engine import reply_classifier as rc
from ai_engine.reply_classifier import (
    apply_auto_action, classify_pending_replies, classify_reply,
)
from inbox.models import EmailMessage
from integrations.models import FollowUpSequence, SuppressionEntry


def _llm(user):
    from integrations.models import APIIntegration
    integ = APIIntegration(user=user, provider='anthropic', model='claude-opus-5', is_primary=True)
    integ.set_api_key('sk-test')
    integ.save()


def _inbound(user, lead, body, subject='Re: your email', intent=''):
    return EmailMessage.objects.create(
        user=user, lead=lead, message_id=f'<{timezone.now().timestamp()}@x.test>',
        from_email=lead.email, to_email='me@acme.test', subject=subject,
        body_text=body, received_at=timezone.now(), direction='inbound', intent=intent,
    )


# --------------------------------------------------------------------------
# Heuristics (no LLM call)
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_out_of_office_is_caught_by_heuristic(user_a):
    assert classify_reply(user_a, 'Automatic reply', 'I am out of office until Monday.') == 'out_of_office'


@pytest.mark.django_db
def test_unsubscribe_is_caught_by_heuristic(user_a):
    assert classify_reply(user_a, 'Re: hi', 'Please unsubscribe me from this list.') == 'unsubscribe'
    assert classify_reply(user_a, 'stop', 'take me off your list') == 'unsubscribe'


@pytest.mark.django_db
def test_heuristic_skips_the_llm(user_a, monkeypatch):
    from ai_engine import providers
    monkeypatch.setattr(providers, 'generate',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('should not call LLM')))
    assert classify_reply(user_a, 'OOO', 'out of office, back next week') == 'out_of_office'


# --------------------------------------------------------------------------
# LLM path
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_llm_classifies_interested(user_a, monkeypatch):
    _llm(user_a)
    from ai_engine import providers
    monkeypatch.setattr(providers, 'generate', lambda *a, **k: '{"intent": "interested"}')
    assert classify_reply(user_a, 'Re: hi', "Sure, I'd love to hear more. When are you free?") == 'interested'


@pytest.mark.django_db
def test_llm_parses_bare_label(user_a, monkeypatch):
    _llm(user_a)
    from ai_engine import providers
    monkeypatch.setattr(providers, 'generate', lambda *a, **k: 'not_interested')
    assert classify_reply(user_a, 'Re: hi', 'No thanks, not a fit for us.') == 'not_interested'


@pytest.mark.django_db
def test_unknown_label_falls_back_to_other(user_a, monkeypatch):
    _llm(user_a)
    from ai_engine import providers
    monkeypatch.setattr(providers, 'generate', lambda *a, **k: '{"intent": "banana"}')
    assert classify_reply(user_a, 'Re: hi', 'maybe') == 'other'


@pytest.mark.django_db
def test_provider_failure_falls_back_to_other(user_a, monkeypatch):
    _llm(user_a)
    from ai_engine import providers

    def boom(*a, **k):
        raise providers.ProviderError('rate limited')

    monkeypatch.setattr(providers, 'generate', boom)
    assert classify_reply(user_a, 'Re: hi', 'some ambiguous reply') == 'other'


@pytest.mark.django_db
def test_no_provider_returns_other(user_a):
    assert classify_reply(user_a, 'Re: hi', 'ambiguous') == 'other'


# --------------------------------------------------------------------------
# Auto-actions
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_unsubscribe_suppresses_and_blacklists(user_a, lead_a):
    msg = _inbound(user_a, lead_a, 'unsubscribe me', intent='unsubscribe')
    action = apply_auto_action(msg)

    assert action == 'suppressed'
    assert SuppressionEntry.objects.filter(user=user_a, email=lead_a.email).exists()
    lead_a.refresh_from_db()
    assert lead_a.status == 'blacklisted'


@pytest.mark.django_db
def test_unsubscribe_stops_the_followup_sequence(user_a, lead_a):
    seq = FollowUpSequence.objects.create(
        user=user_a, lead=lead_a, next_send_at=timezone.now(), last_sent_at=timezone.now(),
    )
    msg = _inbound(user_a, lead_a, 'please remove me', intent='unsubscribe')
    apply_auto_action(msg)
    seq.refresh_from_db()
    assert seq.status == 'stopped'


@pytest.mark.django_db
def test_out_of_office_defers_followup_without_stopping(user_a, lead_a):
    from datetime import timedelta
    original = timezone.now()
    seq = FollowUpSequence.objects.create(
        user=user_a, lead=lead_a, next_send_at=original, last_sent_at=original,
    )
    msg = _inbound(user_a, lead_a, 'out of office', intent='out_of_office')
    action = apply_auto_action(msg)

    assert action == 'followup_deferred'
    seq.refresh_from_db()
    assert seq.status == 'active'  # NOT stopped
    assert seq.next_send_at > original + timedelta(days=2)


@pytest.mark.django_db
def test_interested_reply_takes_no_auto_action(user_a, lead_a):
    msg = _inbound(user_a, lead_a, "yes let's talk", intent='interested')
    assert apply_auto_action(msg) == ''
    lead_a.refresh_from_db()
    assert lead_a.status != 'blacklisted'


# --------------------------------------------------------------------------
# Batch processing
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_batch_classifies_and_acts(user_a, lead_a, monkeypatch):
    _llm(user_a)
    _inbound(user_a, lead_a, 'please unsubscribe me')  # heuristic -> unsubscribe

    from ai_engine import providers
    monkeypatch.setattr(providers, 'generate', lambda *a, **k: '{"intent": "other"}')

    result = classify_pending_replies(user_a)
    assert result['classified'] == 1
    assert result['actions'].get('suppressed') == 1

    msg = EmailMessage.objects.get(user=user_a, direction='inbound')
    assert msg.intent == 'unsubscribe'
    assert msg.intent_classified_at is not None


@pytest.mark.django_db
def test_batch_skips_already_classified(user_a, lead_a, monkeypatch):
    _inbound(user_a, lead_a, 'hi', intent='interested')
    from ai_engine import providers
    monkeypatch.setattr(providers, 'generate',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('should not reclassify')))
    assert classify_pending_replies(user_a)['classified'] == 0


@pytest.mark.django_db
def test_batch_is_capped(user_a, lead_a, monkeypatch):
    for i in range(rc.MAX_PER_BATCH + 10):
        EmailMessage.objects.create(
            user=user_a, lead=lead_a, message_id=f'<cap{i}@x.test>',
            from_email=lead_a.email, to_email='me@acme.test', subject='Re',
            body_text='ambiguous', received_at=timezone.now(), direction='inbound',
        )
    from ai_engine import providers
    monkeypatch.setattr(providers, 'generate', lambda *a, **k: '{"intent": "other"}')
    assert classify_pending_replies(user_a)['classified'] == rc.MAX_PER_BATCH


@pytest.mark.django_db
def test_intent_is_exposed_in_inbox_api(auth_a, user_a, lead_a):
    _inbound(user_a, lead_a, 'yes interested', intent='interested')
    threads = auth_a.get('/api/inbox/').json()
    messages = threads[0]['messages'] if isinstance(threads, list) and threads else []
    assert any(m.get('intent') == 'interested' for m in messages)
    assert any(m.get('intent_label') == 'Interested' for m in messages)


@pytest.mark.django_db
def test_classification_is_tenant_scoped(user_a, user_b, lead_a):
    _inbound(user_b, lead_a, 'unsubscribe')  # belongs to B (lead_a is A's; cross-tenant inbound is contrived)
    # user_a has nothing unclassified of their own
    assert classify_pending_replies(user_a)['classified'] == 0
