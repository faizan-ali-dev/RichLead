import pytest
from django.core import mail
from django.core.cache import cache
from django.test import override_settings


@pytest.mark.django_db
def test_profile_settings_hide_username_and_allow_name_and_nickname_edits(auth_a, user_a):
    response = auth_a.get('/api/users/settings/')

    assert response.status_code == 200
    assert 'username' not in response.data
    assert response.data['full_name'] == ''
    assert response.data['nickname'] == ''
    assert response.data['email'] == user_a.email

    updated = auth_a.patch('/api/users/profile/', {
        'full_name': '  Alice   Example  ',
        'nickname': '  Ali   E  ',
    }, format='json')

    assert updated.status_code == 200
    assert updated.data == {
        'success': True,
        'full_name': 'Alice Example',
        'nickname': 'Ali E',
        'email': user_a.email,
    }
    user_a.refresh_from_db()
    assert user_a.first_name == 'Alice'
    assert user_a.last_name == 'Example'
    assert user_a.nickname == 'Ali E'


@pytest.mark.django_db
@override_settings(
    PASSWORD_RESET_EMAIL_ENABLED=True,
    MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}},
    PASSWORD_RESET_SENDER_ADDRESS='verify@example.test',
    PASSWORD_RESET_FROM_NAME='Rich Lead',
)
def test_email_change_requires_new_address_code_and_notifies_old_address(auth_a, user_a):
    cache.clear()
    mail.outbox.clear()

    requested = auth_a.post('/api/users/profile/email-change/', {
        'new_email': 'NEW.Address@example.test',
    }, format='json')

    assert requested.status_code == 202
    assert requested.data['pending_email'] == 'new.address@example.test'
    user_a.refresh_from_db()
    assert user_a.email == 'alice@acme.test'
    assert user_a.pending_email == 'new.address@example.test'
    assert len(mail.outbox) == 2
    assert mail.outbox[0].to == ['new.address@example.test']
    assert mail.outbox[1].to == ['alice@acme.test']

    code = mail.outbox[0].body.split('email-change code is ', 1)[1].split('.', 1)[0]
    confirmed = auth_a.post('/api/users/profile/email-change/confirm/', {'code': code}, format='json')

    assert confirmed.status_code == 200
    assert confirmed.data['email'] == 'new.address@example.test'
    user_a.refresh_from_db()
    assert user_a.email == 'new.address@example.test'
    assert user_a.email_verified is True
    assert user_a.pending_email == ''
    assert user_a.email_change_code_hash == ''
    assert mail.outbox[-1].to == ['alice@acme.test']
    assert 'was changed' in mail.outbox[-1].subject


@pytest.mark.django_db
@override_settings(
    PASSWORD_RESET_EMAIL_ENABLED=True,
    MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}},
)
def test_email_change_rejects_an_address_already_used_by_another_account(auth_a, user_b):
    cache.clear()

    response = auth_a.post('/api/users/profile/email-change/', {
        'new_email': user_b.email,
    }, format='json')

    assert response.status_code == 400
    assert 'already linked' in response.data['detail']
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(PASSWORD_RESET_EMAIL_ENABLED=False)
def test_email_change_does_not_mutate_account_when_email_delivery_is_unavailable(auth_a, user_a):
    cache.clear()

    response = auth_a.post('/api/users/profile/email-change/', {
        'new_email': 'new@example.test',
    }, format='json')

    assert response.status_code == 503
    user_a.refresh_from_db()
    assert user_a.email == 'alice@acme.test'
    assert user_a.pending_email == ''
