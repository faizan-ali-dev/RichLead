from datetime import timedelta

import pytest
from django.utils import timezone

from inbox.models import EmailMessage
from integrations.models import EmailAccount


@pytest.mark.django_db
def test_inbox_threads_report_message_count_and_mailbox(auth_a, user_a, lead_a):
    account = EmailAccount.objects.create(
        user=user_a, email_address='sales@acme.test', provider='smtp', is_connected=True,
    )
    now = timezone.now()
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, account=account, message_id='thread-outbound-1',
        direction='outbound', from_email=account.email_address, to_email=lead_a.email,
        subject='Intro', body_text='Hello', received_at=now - timedelta(hours=1),
    )
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, account=account, message_id='thread-inbound-1',
        direction='inbound', from_email=lead_a.email, to_email=account.email_address,
        subject='Re: Intro', body_text='Please send details', received_at=now,
    )

    response = auth_a.get('/api/inbox/')

    assert response.status_code == 200
    thread = response.data[0]
    assert thread['message_count'] == 2
    assert thread['unread_count'] == 1
    assert thread['mailbox_email'] == account.email_address
    assert {message['account_email'] for message in thread['messages']} == {account.email_address}


@pytest.mark.django_db
def test_reply_notifications_group_unread_messages_and_opening_marks_them_read(auth_a, user_a, lead_a):
    account = EmailAccount.objects.create(
        user=user_a, email_address='sales@acme.test', provider='smtp', is_connected=True,
    )
    now = timezone.now()
    for index in range(2):
        EmailMessage.objects.create(
            user=user_a, lead=lead_a, account=account, message_id=f'unread-reply-{index}',
            direction='inbound', from_email=lead_a.email, to_email=account.email_address,
            subject=f'Reply {index}', body_text=f'New response {index}',
            received_at=now - timedelta(minutes=index),
        )

    notifications = auth_a.get('/api/inbox/notifications/')
    assert notifications.status_code == 200
    assert notifications.data['unread_count'] == 2
    assert len(notifications.data['notifications']) == 1
    assert notifications.data['notifications'][0]['unread_count'] == 2
    assert notifications.data['notifications'][0]['account_email'] == account.email_address

    opened = auth_a.post(f'/api/inbox/{lead_a.pk}/read/')
    assert opened.status_code == 200
    assert opened.data['marked_read'] == 2
    assert auth_a.get('/api/inbox/notifications/').data['unread_count'] == 0


@pytest.mark.django_db
def test_notification_and_mark_read_are_scoped_to_current_user(auth_a, auth_b, user_a, lead_a):
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, message_id='private-unread-reply', direction='inbound',
        from_email=lead_a.email, to_email=user_a.email, subject='Private reply',
        body_text='Private body', received_at=timezone.now(),
    )

    assert auth_b.get('/api/inbox/notifications/').data['unread_count'] == 0
    assert auth_b.post(f'/api/inbox/{lead_a.pk}/read/').status_code == 404


@pytest.mark.django_db
def test_inbox_reply_shows_new_text_and_a_compact_replied_to_excerpt(auth_a, user_a, lead_a):
    account = EmailAccount.objects.create(
        user=user_a, email_address='sales@acme.test', provider='smtp', is_connected=True,
    )
    now = timezone.now()
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, account=account, message_id='quoted-outbound',
        direction='outbound', from_email=account.email_address, to_email=lead_a.email,
        subject='Re: rebuilding infrastructure too often',
        body_text='I noticed you run Kareem Niaz in the electronics space. We help automate order logging and inventory updates so you can focus on sales.',
        received_at=now - timedelta(minutes=1),
    )
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, account=account, message_id='quoted-inbound',
        direction='inbound', from_email=lead_a.email, to_email=account.email_address,
        subject='Re: rebuilding infrastructure too often',
        body_text='OK\n\nOn Sat, 3 Oct 2026 at 04:13, Faizan Ali <faizanali@example.com> wrote:\n> I noticed you run Kareem Niaz in the electronics space.\n> We help automate order logging and inventory updates.',
        received_at=now,
    )

    response = auth_a.get('/api/inbox/')

    assert response.status_code == 200
    messages = response.data[0]['messages']
    reply = next(message for message in messages if message['direction'] == 'inbound')
    assert reply['body_text'] == 'OK'
    assert 'I noticed you run Kareem Niaz' not in reply['body_html']
    assert reply['reply_to_preview'].startswith('I noticed you run Kareem Niaz')
    assert len(reply['reply_to_preview']) <= 120


@pytest.mark.django_db
def test_reply_notification_preview_excludes_quoted_original(auth_a, user_a, lead_a):
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, message_id='notification-quoted-reply', direction='inbound',
        from_email=lead_a.email, to_email=user_a.email, subject='Re: Intro',
        body_text='Sounds good.\n\nOn Sat, 3 Oct 2026 at 04:13, Faizan Ali wrote:\n> Original outreach text',
        received_at=timezone.now(),
    )

    response = auth_a.get('/api/inbox/notifications/')

    assert response.status_code == 200
    assert response.data['notifications'][0]['preview'] == 'Sounds good.'
