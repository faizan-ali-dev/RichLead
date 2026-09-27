from django.conf import settings
from richlead_backend.settings import _postgres_database_config


def test_collectstatic_has_a_configured_destination():
    assert settings.STATIC_ROOT


def test_database_url_selects_postgresql_with_tls():
    database = _postgres_database_config('postgresql://richlead:secret@db.example.test:5432/richlead')
    assert database['ENGINE'] == 'django.db.backends.postgresql'
    assert database['HOST'] == 'db.example.test'
    assert database['OPTIONS']['sslmode'] == 'require'
    assert database['NAME'] == 'richlead'
