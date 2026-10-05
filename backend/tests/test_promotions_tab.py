"""Gmail Promotions-tab placement.

Distinct from spam: these messages pass every filter, Gmail just categorises
them as marketing. Several fixes here reverse choices that help with spam.
"""
import pytest

from ai_engine.prompt_rules import HARD_RULES, PRIMARY_TAB_RULES, analyze_promotions_risk
from integrations.services import (
    _unsubscribe_headers, apply_unsubscribe_text, send_outreach_email,
)


# --------------------------------------------------------------------------
# Structural signals
# --------------------------------------------------------------------------

def test_plain_personal_email_scores_well():
    result = analyze_promotions_risk(
        'list building eating your mornings',
        "Hi Carol, noticed you're hiring two more SDRs. That usually means someone "
        "is burning the first hour on lists. I cut that to ten minutes for a team "
        "your size last month. Worth a look?",
    )
    assert result['score'] >= 90
    assert result['grade'] in ('excellent', 'good')


def test_html_body_is_the_heaviest_signal():
    result = analyze_promotions_risk('subject', 'body', is_html=True)
    html = [i for i in result['issues'] if 'html' in i['message'].lower()]
    assert html and html[0]['severity'] == 'high'


def test_multipart_wrapper_is_flagged():
    result = analyze_promotions_risk('subject', 'body', is_multipart=True)
    assert any('multipart' in i['message'].lower() for i in result['issues'])


def test_tracking_pixel_is_flagged():
    result = analyze_promotions_risk('subject', 'body', has_tracking_pixel=True)
    assert any('tracking pixel' in i['message'].lower() for i in result['issues'])


def test_unsubscribe_header_is_flagged_as_a_promotions_signal():
    """The header helps with spam and hurts with the tab. Both must be surfaced."""
    result = analyze_promotions_risk('subject', 'body', has_unsubscribe_header=True)
    unsub = [i for i in result['issues'] if 'list-unsubscribe' in i['message'].lower()]
    assert unsub and unsub[0]['severity'] == 'high'
    assert '5,000' in unsub[0]['message']


# --------------------------------------------------------------------------
# Content signals
# --------------------------------------------------------------------------

def test_single_link_is_penalised():
    result = analyze_promotions_risk('subject', 'Take a look at https://acme.com for details. Worth a chat?')
    assert any('link' in i['message'].lower() for i in result['issues'])


def test_multiple_links_are_high_severity():
    result = analyze_promotions_risk(
        'subject', 'See https://a.com and https://b.com and https://c.com. Worth a chat?')
    links = [i for i in result['issues'] if 'links' in i['message'].lower()]
    assert links and links[0]['severity'] == 'high'


def test_marketing_vocabulary_is_flagged():
    result = analyze_promotions_risk(
        'our platform',
        'Our industry-leading solution helps streamline your workflow and drive results. Book a demo?',
    )
    messages = ' '.join(i['message'] for i in result['issues'])
    assert 'solution' in messages
    assert 'book a demo' in messages
    assert result['grade'] in ('needs work', 'high spam risk')


def test_unfilled_merge_token_is_high_severity():
    result = analyze_promotions_risk('subject', 'Hi {{first_name}}, quick note about your team.')
    merge = [i for i in result['issues'] if 'merge' in i['message'].lower()]
    assert merge and merge[0]['severity'] == 'high'


def test_generic_greeting_is_flagged():
    result = analyze_promotions_risk('subject', 'Hi there, I wanted to tell you about our product.')
    assert any('merge' in i['message'].lower() or 'bulk' in i['message'].lower()
               for i in result['issues'])


def test_footer_style_unsubscribe_wording_is_flagged():
    result = analyze_promotions_risk('subject', 'Some body copy here.\n\nUnsubscribe from these emails')
    assert any('footer-style' in i['message'].lower() for i in result['issues'])


# --------------------------------------------------------------------------
# Prompt rules
# --------------------------------------------------------------------------

def test_primary_tab_rules_are_always_applied():
    assert PRIMARY_TAB_RULES in HARD_RULES


def test_primary_tab_rules_ban_links_and_marketing_words():
    lowered = PRIMARY_TAB_RULES.lower()
    assert 'do not include any link in a first touch' in lowered
    assert 'industry-leading' in lowered
    assert 'book a demo' in lowered
    assert 'no signature block' in lowered


@pytest.mark.django_db
def test_prompt_rules_endpoint_exposes_the_primary_tab_section(auth_a):
    resp = auth_a.get('/api/ai/prompt-rules/')
    titles = [s['title'] for s in resp.json()['sections']]
    assert 'Primary tab (not Promotions)' in titles


# --------------------------------------------------------------------------
# Unsubscribe mode: the actual trade-off
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_text_mode_omits_the_header(user_a, lead_a):
    user_a.unsubscribe_mode = 'text'
    user_a.save()
    assert _unsubscribe_headers(user_a, lead_a) == {}


@pytest.mark.django_db
def test_header_mode_includes_the_header(user_a, lead_a):
    user_a.unsubscribe_mode = 'header'
    user_a.save()
    headers = _unsubscribe_headers(user_a, lead_a)
    assert 'List-Unsubscribe' in headers
    assert headers['List-Unsubscribe-Post'] == 'List-Unsubscribe=One-Click'


@pytest.mark.django_db
def test_both_mode_includes_header_and_text(user_a, lead_a):
    user_a.unsubscribe_mode = 'both'
    user_a.save()
    assert 'List-Unsubscribe' in _unsubscribe_headers(user_a, lead_a)
    assert user_a.unsubscribe_text in apply_unsubscribe_text(user_a, 'Body here.')


@pytest.mark.django_db
def test_text_mode_appends_the_optout_line(user_a):
    user_a.unsubscribe_mode = 'text'
    user_a.save()
    result = apply_unsubscribe_text(user_a, 'Body here.')
    assert result.startswith('Body here.')
    assert "no thanks" in result


@pytest.mark.django_db
def test_header_mode_does_not_append_text(user_a):
    user_a.unsubscribe_mode = 'header'
    user_a.save()
    assert apply_unsubscribe_text(user_a, 'Body here.') == 'Body here.'


@pytest.mark.django_db
def test_optout_line_is_not_duplicated(user_a):
    user_a.unsubscribe_mode = 'text'
    user_a.save()
    once = apply_unsubscribe_text(user_a, 'Body here.')
    twice = apply_unsubscribe_text(user_a, once)
    assert once == twice


@pytest.mark.django_db
def test_default_mode_is_text_for_primary_placement(user_a):
    """Default must favour Primary; bulk senders opt into the header."""
    assert user_a.unsubscribe_mode == 'text'


@pytest.mark.django_db
def test_every_mode_still_provides_an_optout(user_a, lead_a):
    """Compliance is non-negotiable regardless of which mode is chosen."""
    for mode in ('text', 'header', 'both'):
        user_a.unsubscribe_mode = mode
        user_a.save()
        has_header = bool(_unsubscribe_headers(user_a, lead_a))
        has_text = apply_unsubscribe_text(user_a, 'Body.') != 'Body.'
        assert has_header or has_text, f'mode {mode} provides no opt-out'


# --------------------------------------------------------------------------
# MIME structure on the wire
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_smtp_sends_bare_text_plain_not_multipart(user_a, lead_a, monkeypatch):
    """A single-part multipart/mixed wrapper marks the mail as machine-built."""
    from integrations.models import EmailAccount

    account = EmailAccount.objects.create(
        user=user_a, email_address='me@acme.test', auth_type='smtp',
        smtp_host='smtp.acme.test', smtp_port=587, is_connected=True,
    )
    account.set_password('pw')
    account.save()

    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def starttls(self, *a, **k):
            pass

        def login(self, *a):
            pass

        def send_message(self, msg):
            sent['msg'] = msg

        def quit(self):
            pass

    monkeypatch.setattr('integrations.services.validate_public_mail_server', lambda *a, **k: None)
    monkeypatch.setattr('integrations.services.connect_smtp', lambda *a, **k: FakeSMTP())

    result = send_outreach_email(lead_a.id, user_a, 'A short personal note. Worth a look?')
    assert result['success'] is True

    msg = sent['msg']
    assert msg.get_content_type() == 'text/plain'
    assert not msg.is_multipart()


@pytest.mark.django_db
def test_smtp_respects_unsubscribe_mode(user_a, lead_a, monkeypatch):
    from integrations.models import EmailAccount

    account = EmailAccount.objects.create(
        user=user_a, email_address='me@acme.test', auth_type='smtp',
        smtp_host='smtp.acme.test', smtp_port=587, is_connected=True,
    )
    account.set_password('pw')
    account.save()

    user_a.unsubscribe_mode = 'text'
    user_a.save()

    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def starttls(self, *a, **k):
            pass

        def login(self, *a):
            pass

        def send_message(self, msg):
            sent['msg'] = msg

        def quit(self):
            pass

    monkeypatch.setattr('integrations.services.validate_public_mail_server', lambda *a, **k: None)
    monkeypatch.setattr('integrations.services.connect_smtp', lambda *a, **k: FakeSMTP())
    send_outreach_email(lead_a.id, user_a, 'A short personal note. Worth a look?')

    msg = sent['msg']
    assert msg.get('List-Unsubscribe') is None
    assert 'no thanks' in msg.get_payload(decode=True).decode()


# --------------------------------------------------------------------------
# Settings plumbing
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_settings_round_trip(auth_a):
    resp = auth_a.post('/api/users/settings/',
                       {'unsubscribe_mode': 'header'}, format='json')
    assert resp.status_code == 200
    assert resp.json()['unsubscribe_mode'] == 'header'
    assert auth_a.get('/api/users/settings/').json()['unsubscribe_mode'] == 'header'


@pytest.mark.django_db
def test_invalid_unsubscribe_mode_is_rejected(auth_a):
    resp = auth_a.post('/api/users/settings/', {'unsubscribe_mode': 'nonsense'}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_empty_unsubscribe_text_is_rejected(auth_a):
    resp = auth_a.post('/api/users/settings/', {'unsubscribe_text': '   '}, format='json')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_spam_check_endpoint_returns_both_scores(auth_a):
    resp = auth_a.post('/api/ai/spam-check/', {
        'subject': 'our industry-leading platform',
        'body': 'Our solution helps streamline your workflow. Book a demo at https://acme.com',
    }, format='json')
    assert resp.status_code == 200
    data = resp.json()
    assert 'score' in data           # spam
    assert 'promotions' in data      # tab placement
    assert data['promotions']['score'] < data['score'], 'promo risk should dominate here'
