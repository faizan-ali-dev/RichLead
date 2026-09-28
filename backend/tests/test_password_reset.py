from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

User = get_user_model()


def test_signup_accepts_full_name_email_and_password_only(db):
    response = APIClient().post('/api/users/register/', {
        'full_name': '  Samira   Khan  ',
        'email': 'SAMIRA@example.test',
        'password': 'Good-password-429!',
    }, format='json')

    assert response.status_code == 201
    assert 'username' not in response.data
    user = User.objects.get(email='samira@example.test')
    assert user.get_full_name() == 'Samira Khan'
    assert user.check_password('Good-password-429!')
    assert user.username and user.username != 'samira@example.test'


@override_settings(
    PASSWORD_RESET_EMAIL_ENABLED=True,
    MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}},
    FRONTEND_URL='https://richlead.elevabel.com',
    PASSWORD_RESET_SENDER_ADDRESS='reset@example.test',
    PASSWORD_RESET_FROM_NAME='Rich Lead',
)
def test_password_reset_sends_generic_secure_link_for_existing_email(db):
    cache.clear()
    user = User.objects.create_user(
        username='reset-user', email='reset@example.test', password='Original-Password-735!'
    )

    response = APIClient().post(
        '/api/users/password-reset/', {'email': 'RESET@example.test'}, format='json',
    )

    assert response.status_code == 200
    assert response.data['detail'] == 'If an account exists for that email, a reset link will be sent.'
    assert len(mail.outbox) == 1
    assert 'https://richlead.elevabel.com/reset-password?uid=' in mail.outbox[0].body
    assert '&token=' in mail.outbox[0].body
    assert mail.outbox[0].from_email == 'Rich Lead <reset@example.test>'


@override_settings(
    PASSWORD_RESET_EMAIL_ENABLED=True,
    MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}},
)
def test_password_reset_does_not_reveal_unknown_email(db):
    cache.clear()
    client = APIClient(REMOTE_ADDR='192.0.2.14')

    response = client.post(
        '/api/users/password-reset/', {'email': 'unknown@example.test'}, format='json',
    )

    assert response.status_code == 200
    assert response.data['detail'] == 'If an account exists for that email, a reset link will be sent.'
    assert len(mail.outbox) == 0


def test_password_reset_requires_global_smtp_config(db, settings):
    cache.clear()
    settings.PASSWORD_RESET_EMAIL_ENABLED = False

    response = APIClient(REMOTE_ADDR='192.0.2.15').post(
        '/api/users/password-reset/', {'email': 'unknown@example.test'}, format='json',
    )

    assert response.status_code == 503


def test_password_reset_confirm_updates_password_and_invalidates_token(db):
    user = User.objects.create_user(
        username='reset-user', email='reset@example.test', password='Original-Password-735!'
    )
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    payload = {
        'uid': uid,
        'token': token,
        'new_password': 'Different-Password-946!',
    }
    client = APIClient(REMOTE_ADDR='192.0.2.16')

    response = client.post('/api/users/password-reset/confirm/', payload, format='json')

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password('Different-Password-946!')
    assert not default_token_generator.check_token(user, token)


def test_password_reset_confirm_rejects_invalid_token(db):
    User.objects.create_user(
        username='reset-user', email='reset@example.test', password='Original-Password-735!'
    )
    uid = urlsafe_base64_encode(force_bytes('reset-user'))

    response = APIClient(REMOTE_ADDR='192.0.2.17').post(
        '/api/users/password-reset/confirm/', {
            'uid': uid,
            'token': 'invalid-token',
            'new_password': 'Different-Password-946!',
        }, format='json',
    )

    assert response.status_code == 400
