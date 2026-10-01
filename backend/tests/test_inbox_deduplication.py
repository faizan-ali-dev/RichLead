from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from inbox.models import EmailMessage
from inbox.services import record_email_message, same_outbound_body
from leads.models import Lead


@pytest.mark.django_db
def test_sent_message_and_truncated_mailbox_echo_are_saved_once(user_a, lead_a):
    sent_at = timezone.now()
    complete_body = (
        "Hi Carol, you're probably rebuilding the same setup for every deployment. "
        'We help teams standardize those workflows and save time.'
    )
    truncated_echo = complete_body[:125].replace("you're", 'you&#39;re')

    assert record_email_message(
        user=user_a,
        lead=lead_a,
        account=None,
        message_id='sent-rfc-id',
        rfc_message_id='<sent@example.test>',
        subject='Re: rebuilding infrastructure too often',
        from_email=user_a.email,
        to_email=lead_a.email,
        body_text=complete_body,
        received_at=sent_at,
        direction='outbound',
    ) is True

    assert record_email_message(
        user=user_a,
        lead=lead_a,
        account=None,
        message_id='provider-copy-id',
        subject='Re: rebuilding infrastructure too often',
        from_email=user_a.email,
        to_email=lead_a.email,
        body_text=truncated_echo,
        received_at=sent_at + timedelta(seconds=20),
        direction='outbound',
    ) is False

    rows = EmailMessage.objects.filter(user=user_a, lead=lead_a, direction='outbound')
    assert rows.count() == 1
    assert rows.get().body_text == complete_body


@pytest.mark.django_db
def test_sync_first_truncated_copy_is_upgraded_when_full_send_record_arrives(user_a, lead_a):
    sent_at = timezone.now()
    complete_body = 'Hello Carol, ' + ('we can make this process more efficient. ' * 5)
    truncated_echo = complete_body[:120]

    assert record_email_message(
        user=user_a,
        lead=lead_a,
        account=None,
        message_id='provider-copy-id',
        subject='A useful subject',
        from_email=user_a.email,
        to_email=lead_a.email,
        body_text=truncated_echo,
        received_at=sent_at,
        direction='outbound',
    ) is True
    assert record_email_message(
        user=user_a,
        lead=lead_a,
        account=None,
        message_id='sent-send-time-id',
        rfc_message_id='<send-time@example.test>',
        subject='A useful subject',
        from_email=user_a.email,
        to_email=lead_a.email,
        body_text=complete_body,
        received_at=sent_at + timedelta(seconds=10),
        direction='outbound',
    ) is False

    rows = EmailMessage.objects.filter(user=user_a, lead=lead_a, direction='outbound')
    assert rows.count() == 1
    assert rows.get().body_text == complete_body


@pytest.mark.django_db
def test_inbox_hides_legacy_same_minute_echo_without_deleting_rows(user_a, lead_a):
    sent_at = timezone.now().replace(second=0, microsecond=0)
    complete_body = "Hi Carol, you're probably rebuilding the same standard setup for every deployment."
    EmailMessage.objects.create(
        user=user_a,
        lead=lead_a,
        message_id='legacy-short-copy',
        subject='Re: rebuilding infrastructure too often',
        from_email=user_a.email,
        to_email=lead_a.email,
        body_text=complete_body[:105].replace("you're", 'you&#39;re'),
        received_at=sent_at,
        direction='outbound',
    )
    EmailMessage.objects.create(
        user=user_a,
        lead=lead_a,
        message_id='sent-legacy-full-copy',
        subject='Re: rebuilding infrastructure too often',
        from_email=user_a.email,
        to_email=lead_a.email,
        body_text=complete_body,
        received_at=sent_at + timedelta(seconds=20),
        direction='outbound',
    )

    client = APIClient()
    client.force_authenticate(user=user_a)
    response = client.get('/api/inbox/')

    assert response.status_code == 200
    thread = next(item for item in response.json() if item['lead_id'] == lead_a.id)
    outbound = [message for message in thread['messages'] if message['direction'] == 'outbound']
    assert len(outbound) == 1
    assert outbound[0]['body_text'] == complete_body
    assert EmailMessage.objects.filter(user=user_a, lead=lead_a, direction='outbound').count() == 2


@pytest.mark.django_db
def test_distinct_outbound_content_is_not_merged_for_same_subject(user_a, lead_a):
    sent_at = timezone.now()
    assert record_email_message(
        user=user_a,
        lead=lead_a,
        account=None,
        message_id='sent-send-one',
        subject='Checking in',
        from_email=user_a.email,
        to_email=lead_a.email,
        body_text='A first message with a distinct body.' * 4,
        received_at=sent_at,
        direction='outbound',
    ) is True
    assert record_email_message(
        user=user_a,
        lead=lead_a,
        account=None,
        message_id='sent-send-two',
        subject='Checking in',
        from_email=user_a.email,
        to_email=lead_a.email,
        body_text='A different message with another distinct body.' * 4,
        received_at=sent_at + timedelta(seconds=30),
        direction='outbound',
    ) is True
    assert EmailMessage.objects.filter(user=user_a, lead=lead_a, direction='outbound').count() == 2


@pytest.mark.django_db
def test_two_distinct_send_records_with_same_body_are_not_collapsed(user_a, lead_a):
    sent_at = timezone.now().replace(second=0, microsecond=0)
    same_body = 'A repeated approved campaign message, sent intentionally.' * 3
    for message_id, offset in (('sent-first-send', 0), ('sent-second-send', 20)):
        assert record_email_message(
            user=user_a,
            lead=lead_a,
            account=None,
            message_id=message_id,
            subject='A useful subject',
            from_email=user_a.email,
            to_email=lead_a.email,
            body_text=same_body,
            received_at=sent_at + timedelta(seconds=offset),
            direction='outbound',
        ) is True

    client = APIClient()
    client.force_authenticate(user=user_a)
    response = client.get('/api/inbox/')
    thread = next(item for item in response.json() if item['lead_id'] == lead_a.id)
    outbound = [message for message in thread['messages'] if message['direction'] == 'outbound']
    assert len(outbound) == 2


def test_outbound_body_matching_handles_escaped_entities_but_not_unrelated_bodies():
    complete_body = "Hi Casey, you're probably rebuilding a standard process repeatedly. " * 3
    assert same_outbound_body(complete_body, complete_body[:125].replace("you're", 'you&#39;re'))
    assert not same_outbound_body(complete_body, 'A different message.' * 8)
