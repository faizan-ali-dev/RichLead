"""P1: authentication hardening."""
from datetime import timedelta

import pytest
from django.conf import settings


def test_access_token_is_short_lived():
    """A 30-day access token cannot be revoked and is a month-long bearer secret."""
    assert settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'] <= timedelta(hours=1)


def test_refresh_tokens_rotate_and_blacklist():
    assert settings.SIMPLE_JWT['ROTATE_REFRESH_TOKENS'] is True
    assert settings.SIMPLE_JWT['BLACKLIST_AFTER_ROTATION'] is True
    assert 'rest_framework_simplejwt.token_blacklist' in settings.INSTALLED_APPS


@pytest.mark.django_db
def test_login_returns_both_tokens(api, user_a):
    resp = api.post('/api/token/', {'username': 'alice', 'password': 'Str0ng!Pass2026'}, format='json')
    assert resp.status_code == 200
    assert resp.json().get('access')
    assert resp.json().get('refresh')


@pytest.mark.django_db
def test_refresh_issues_a_new_access_token(api, user_a):
    refresh = api.post(
        '/api/token/', {'username': 'alice', 'password': 'Str0ng!Pass2026'}, format='json'
    ).json()['refresh']

    resp = api.post('/api/token/refresh/', {'refresh': refresh}, format='json')
    assert resp.status_code == 200
    assert resp.json().get('access')


@pytest.mark.django_db
def test_rotated_refresh_token_cannot_be_reused(api, user_a):
    """Replaying a rotated refresh token must fail, or revocation is meaningless."""
    refresh = api.post(
        '/api/token/', {'username': 'alice', 'password': 'Str0ng!Pass2026'}, format='json'
    ).json()['refresh']

    first = api.post('/api/token/refresh/', {'refresh': refresh}, format='json')
    assert first.status_code == 200

    replay = api.post('/api/token/refresh/', {'refresh': refresh}, format='json')
    assert replay.status_code == 401


@pytest.fixture
def signup_enabled(settings, monkeypatch):
    """Registration now gates on email verification: a valid signup sends a code
    and returns 201 only when email delivery is configured. Enable that path and
    stub the sender so tests exercise registration without real SMTP."""
    settings.PASSWORD_RESET_EMAIL_ENABLED = True
    monkeypatch.setattr('users.views._send_email_verification_code', lambda user: None)


@pytest.mark.django_db
def test_duplicate_email_registration_is_rejected(api, signup_enabled):
    payload = {'full_name': 'First User', 'email': 'same@example.test', 'password': 'Str0ng!Pass2026'}
    assert api.post('/api/users/register/', payload, format='json').status_code == 201

    dup = api.post(
        '/api/users/register/',
        {'full_name': 'Second User', 'email': 'same@example.test', 'password': 'Str0ng!Pass2026'},
        format='json',
    )
    assert dup.status_code == 400
    assert 'email' in dup.json()


@pytest.mark.django_db
def test_duplicate_email_is_case_insensitive(api, signup_enabled):
    first = api.post(
        '/api/users/register/',
        {'full_name': 'First User', 'email': 'Same@Example.test', 'password': 'Str0ng!Pass2026'},
        format='json',
    )
    assert first.status_code == 201
    dup = api.post(
        '/api/users/register/',
        {'full_name': 'Second User', 'email': 'same@example.test', 'password': 'Str0ng!Pass2026'},
        format='json',
    )
    assert dup.status_code == 400


@pytest.mark.django_db
def test_weak_password_is_rejected(api):
    # The password validator runs during serializer validation, before the email
    # gate, so this fails with 400 whether or not signup email is configured.
    resp = api.post(
        '/api/users/register/',
        {'full_name': 'Weak User', 'email': 'weak@example.test', 'password': '123'},
        format='json',
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_registration_does_not_echo_the_password(api, signup_enabled):
    resp = api.post(
        '/api/users/register/',
        {'full_name': 'Echo User', 'email': 'echo@example.test', 'password': 'Str0ng!Pass2026'},
        format='json',
    )
    assert 'Str0ng!Pass2026' not in resp.content.decode()
