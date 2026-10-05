"""The mailbox must show one entry per real message.

A sent email is written at send time and then reappears in the mailbox during
the next sync, under the provider's own id. Storing both produced duplicate
thread entries, the second often a truncated HTML preview.
"""
import pytest
from django.utils import timezone

from inbox.models import EmailMessage
from inbox.services import html_to_text, is_already_recorded
from integrations.models import EmailAccount
from integrations.services import send_outreach_email


def _smtp_account(user):
    account = EmailAccount.objects.create(
        user=user, email_address='me@acme.test', auth_type='smtp',
        smtp_host='smtp.acme.test', smtp_port=587, is_connected=True,
    )
    account.set_password('pw')
    account.save()
    return account


class FakeSMTP:
    sent = {}

    def __init__(self, *a, **k):
        pass

    def starttls(self, *a, **k):
        pass

    def login(self, *a):
        pass

    def send_message(self, msg):
        FakeSMTP.sent['msg'] = msg

    def quit(self):
        pass


def _patch_smtp(monkeypatch):
    """Intercept the SSRF-protected send path: skip the public-host DNS check and
    hand back a fake SMTP connection instead of dialing the test host."""
    monkeypatch.setattr('integrations.services.validate_public_mail_server', lambda *a, **k: None)
    monkeypatch.setattr('integrations.services.connect_smtp', lambda *a, **k: FakeSMTP())


# --------------------------------------------------------------------------
# Send records a real Message-ID
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_send_stores_the_real_rfc_message_id(user_a, lead_a, monkeypatch):
    _smtp_account(user_a)
    _patch_smtp(monkeypatch)

    send_outreach_email(lead_a.id, user_a, 'A short note. Worth a look?')

    stored = EmailMessage.objects.get(user=user_a, direction='outbound')
    assert stored.rfc_message_id
    assert stored.rfc_message_id.startswith('<')
    # The stored RFC id must equal the one that actually went out on the wire;
    # this is what a later mailbox sync matches on. The local message_id is a
    # synthetic 'sent-' placeholder (the send happens before the provider assigns
    # its own id), so the dedup relies on rfc_message_id, not message_id.
    assert stored.rfc_message_id == FakeSMTP.sent['msg']['Message-ID']
    assert is_already_recorded(
        user_a, message_id='AAMkAG-provider-assigned', rfc_message_id=stored.rfc_message_id,
        lead=lead_a, direction='outbound', subject=stored.subject,
    ) is True


@pytest.mark.django_db
def test_stored_body_matches_what_was_delivered(user_a, lead_a, monkeypatch):
    _smtp_account(user_a)
    user_a.unsubscribe_mode = 'text'
    user_a.save()
    _patch_smtp(monkeypatch)

    send_outreach_email(lead_a.id, user_a, 'A short note. Worth a look?')

    stored = EmailMessage.objects.get(user=user_a, direction='outbound')
    wire_body = FakeSMTP.sent['msg'].get_payload(decode=True).decode()
    assert stored.body_text == wire_body
    assert 'no thanks' in stored.body_text


# --------------------------------------------------------------------------
# Sync recognises our own sends
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_sync_recognises_our_send_by_rfc_id(user_a, lead_a):
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, message_id='<abc@acme.test>',
        rfc_message_id='<abc@acme.test>', subject='a subject',
        from_email='me@acme.test', to_email=lead_a.email,
        received_at=timezone.now(), direction='outbound',
    )

    # Same message, now seen under the provider's own internal id.
    assert is_already_recorded(
        user_a, message_id='AAMkAGI2provider-id', rfc_message_id='<abc@acme.test>',
        lead=lead_a, direction='outbound', subject='a subject',
    ) is True


@pytest.mark.django_db
def test_sync_recognises_graph_send_without_an_id(user_a, lead_a):
    """Graph's sendMail returns no id, so fall back to lead+subject+body+time.

    The send-time row carries a 'sent-' id and the body; the provider echo arrives
    under Graph's own id with the same body. Matching on body (not just subject)
    avoids collapsing two genuinely different sends that share a subject.
    """
    now = timezone.now()
    body = 'Hi Carol, I noticed Globex is scaling its SaaS motion and wanted to share one idea.'
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, message_id='sent-local', rfc_message_id='',
        subject='Assisting You with Manual Lead Nurturing', body_text=body,
        from_email='me@acme.test', to_email=lead_a.email,
        received_at=now, direction='outbound',
    )

    assert is_already_recorded(
        user_a, message_id='AAMkAGgraph', rfc_message_id='',
        lead=lead_a, direction='outbound',
        subject='Assisting You with Manual Lead Nurturing', body_text=body,
        received_at=now + timezone.timedelta(minutes=3),
    ) is True


@pytest.mark.django_db
def test_a_genuinely_new_message_is_not_suppressed(user_a, lead_a):
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, message_id='<one@acme.test>',
        rfc_message_id='<one@acme.test>', subject='first',
        from_email='me@acme.test', to_email=lead_a.email,
        received_at=timezone.now(), direction='outbound',
    )

    assert is_already_recorded(
        user_a, message_id='<two@acme.test>', rfc_message_id='<two@acme.test>',
        lead=lead_a, direction='outbound', subject='a different subject',
    ) is False


@pytest.mark.django_db
def test_inbound_replies_are_never_suppressed_by_the_echo_rule(user_a, lead_a):
    """The time-window fallback must only ever apply to outbound mail."""
    now = timezone.now()
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, message_id='<sent@acme.test>',
        rfc_message_id='<sent@acme.test>', subject='a subject',
        from_email='me@acme.test', to_email=lead_a.email,
        received_at=now, direction='outbound',
    )

    assert is_already_recorded(
        user_a, message_id='<their-reply@gmail.com>', rfc_message_id='<their-reply@gmail.com>',
        lead=lead_a, direction='inbound', subject='a subject',
        received_at=now + timezone.timedelta(minutes=2),
    ) is False


@pytest.mark.django_db
def test_dedupe_is_tenant_scoped(user_a, user_b, lead_a):
    EmailMessage.objects.create(
        user=user_b, lead=None, message_id='<shared@acme.test>',
        rfc_message_id='<shared@acme.test>', subject='a subject',
        from_email='x@y.test', to_email='z@y.test',
        received_at=timezone.now(), direction='outbound',
    )

    assert is_already_recorded(
        user_a, message_id='<shared@acme.test>', rfc_message_id='<shared@acme.test>',
        lead=lead_a, direction='outbound', subject='a subject',
    ) is False


@pytest.mark.django_db
def test_resync_does_not_duplicate(user_a, lead_a):
    """Running sync twice over the same mailbox must not grow the thread."""
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, message_id='provider-123',
        rfc_message_id='<abc@acme.test>', subject='a subject',
        from_email=lead_a.email, to_email='me@acme.test',
        received_at=timezone.now(), direction='inbound',
    )

    assert is_already_recorded(user_a, message_id='provider-123', direction='inbound') is True


# --------------------------------------------------------------------------
# Body rendering
# --------------------------------------------------------------------------

def test_html_entities_are_decoded():
    """The truncated preview is what rendered "I&#39;m" in the thread."""
    assert html_to_text('<p>I&#39;m keen on helping</p>') == "I'm keen on helping"


def test_html_tags_are_stripped():
    text = html_to_text('<div><p>First line</p><p>Second line</p></div>')
    assert '<' not in text
    assert 'First line' in text and 'Second line' in text


def test_html_line_breaks_become_newlines():
    assert '\n' in html_to_text('Hello<br>World')


def test_script_and_style_are_removed():
    text = html_to_text('<style>.x{color:red}</style><script>alert(1)</script><p>Real text</p>')
    assert 'color' not in text and 'alert' not in text
    assert 'Real text' in text


def test_empty_html_is_safe():
    assert html_to_text('') == ''
    assert html_to_text(None) == ''


# --------------------------------------------------------------------------
# The mailbox only shows mail that actually went out
# --------------------------------------------------------------------------

@pytest.mark.django_db
def test_sandbox_send_is_not_written_to_the_mailbox(user_a, lead_a, settings):
    """Sandbox mail reached nobody, so it must not appear as sent correspondence."""
    settings.ALLOW_SANDBOX_SEND = True

    result = send_outreach_email(lead_a.id, user_a, 'A short note. Worth a look?')

    assert result['success'] is True and result['sandbox'] is True
    assert EmailMessage.objects.filter(user=user_a).count() == 0


@pytest.mark.django_db
def test_failed_send_is_not_written_to_the_mailbox(user_a, lead_a):
    """No connected mailbox means nothing was sent, so nothing should be recorded."""
    result = send_outreach_email(lead_a.id, user_a, 'A short note.')

    assert result['success'] is False
    assert EmailMessage.objects.filter(user=user_a).count() == 0


@pytest.mark.django_db
def test_successful_send_is_written_once(user_a, lead_a, monkeypatch):
    _smtp_account(user_a)
    _patch_smtp(monkeypatch)

    send_outreach_email(lead_a.id, user_a, 'A short note. Worth a look?')

    assert EmailMessage.objects.filter(user=user_a, direction='outbound').count() == 1


@pytest.mark.django_db
def test_thread_view_shows_one_entry_per_send(auth_a, user_a, lead_a, monkeypatch):
    _smtp_account(user_a)
    _patch_smtp(monkeypatch)

    send_outreach_email(lead_a.id, user_a, 'A short note. Worth a look?')

    threads = auth_a.get('/api/inbox/').json()
    assert len(threads) == 1
    assert len(threads[0]['messages']) == 1
