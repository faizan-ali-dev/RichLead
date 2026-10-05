"""P0-4: credential encryption must use a key from the environment and fail loudly."""
import pytest

from integrations.models import encrypt_key, decrypt_key, APIIntegration, EmailAccount


def test_no_hardcoded_key_in_source():
    """The original fallback key was committed to the repo, making encryption decorative."""
    import inspect
    import integrations.models as m

    source = inspect.getsource(m)
    assert 'K8Q7bLq9P8eB_fW1R2M3sO4T5zY6aX7cV8N9M0L1K2J=' not in source


def test_settings_does_not_define_a_default_fernet_key():
    import inspect
    from django.conf import settings

    # Key must come from the environment, never from a literal default.
    assert getattr(settings, 'FERNET_KEY', None), "FERNET_KEY must be configured"
    src = inspect.getsource(__import__('richlead_backend.settings', fromlist=['x']))
    assert "FERNET_KEY = os.getenv('FERNET_KEY', '" not in src


def test_round_trip_encryption():
    secret = "sk-test-abc123"
    blob = encrypt_key(secret)

    assert blob != secret
    assert secret not in blob
    assert decrypt_key(blob) == secret


def test_decrypt_raises_on_corrupt_ciphertext():
    """The original returned the raw ciphertext on failure, silently sending garbage
    as an SMTP password instead of surfacing a key-rotation bug."""
    from cryptography.fernet import InvalidToken

    with pytest.raises(InvalidToken):
        decrypt_key("this-is-not-valid-ciphertext")


def test_empty_values_pass_through():
    assert decrypt_key('') == ''
    assert decrypt_key(None) is None
    assert encrypt_key('') == ''


@pytest.mark.django_db
def test_api_key_is_encrypted_at_rest(user_a):
    integration = APIIntegration(user=user_a, provider='openai')
    integration.set_api_key('sk-live-supersecret')
    integration.save()

    integration.refresh_from_db()
    assert 'sk-live-supersecret' not in integration.encrypted_api_key
    assert integration.get_api_key() == 'sk-live-supersecret'


@pytest.mark.django_db
def test_smtp_password_is_encrypted_at_rest(user_a):
    account = EmailAccount(user=user_a, email_address='s@x.test', auth_type='smtp')
    account.set_password('hunter2')
    account.save()

    account.refresh_from_db()
    assert 'hunter2' not in account.encrypted_password
    assert account.get_password() == 'hunter2'
