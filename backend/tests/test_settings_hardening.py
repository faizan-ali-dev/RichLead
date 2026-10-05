"""P0-6: secure-by-default DRF and Django configuration."""
import pytest
from django.conf import settings


def test_permissions_deny_by_default():
    """Without this, any view missing @permission_classes is world-readable."""
    defaults = settings.REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']
    assert 'rest_framework.permissions.IsAuthenticated' in defaults


def test_pagination_is_configured():
    assert settings.REST_FRAMEWORK.get('DEFAULT_PAGINATION_CLASS')
    assert settings.REST_FRAMEWORK.get('PAGE_SIZE')


def test_throttling_is_configured():
    rates = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']
    for scope in ('anon', 'user', 'login'):
        assert rates.get(scope), f"missing throttle rate for {scope}"


def test_cors_is_not_wide_open():
    assert getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False) is False
    assert settings.CORS_ALLOWED_ORIGINS


def test_allowed_hosts_has_no_wildcard():
    assert '*' not in settings.ALLOWED_HOSTS


def test_mailers_is_configured():
    """MAILERS is the Django 6.1+ setting; EMAIL_BACKEND is removed in 7.0."""
    assert settings.MAILERS['default']['BACKEND']


def test_every_api_view_declares_its_permissions():
    """Deny-by-default silently 401s views that used to rely on the AllowAny default.

    Public endpoints (OAuth callbacks, unsubscribe) must opt out *explicitly*, so an
    omission is a visible bug rather than a broken user flow discovered in production.
    """
    import pathlib

    offenders = []
    for path in sorted(pathlib.Path('.').rglob('*.py')):
        if 'venv' in str(path) or 'migrations' in str(path) or 'tests' in str(path):
            continue
        lines = path.read_text().split('\n')
        for i, line in enumerate(lines):
            if not line.strip().startswith('@api_view'):
                continue
            j, decorators = i + 1, []
            while j < len(lines) and not lines[j].strip().startswith('def '):
                decorators.append(lines[j])
                j += 1
            if not any('permission_classes' in d for d in decorators):
                name = lines[j].strip() if j < len(lines) else '<unknown>'
                offenders.append(f"{path}:{i + 1} {name}")

    assert not offenders, "views without explicit permission_classes:\n  " + "\n  ".join(offenders)


@pytest.mark.django_db
def test_health_endpoint_is_public(api):
    resp = api.get('/healthz/')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'


@pytest.mark.django_db
def test_list_endpoints_are_paginated(auth_a, user_a):
    from leads.models import Lead
    for i in range(3):
        Lead.objects.create(user=user_a, name=f"L{i}", company="C", niche="n", email=f"p{i}@x.test")

    body = auth_a.get('/api/leads/').json()
    assert isinstance(body, dict)
    assert 'results' in body and 'count' in body
    assert body['count'] == 3


@pytest.mark.django_db
def test_unauthenticated_access_is_refused(api):
    for path in ('/api/leads/', '/api/inbox/', '/api/integrations/suppression/', '/api/dashboard/stats/'):
        assert api.get(path).status_code in (401, 403), path


@pytest.mark.django_db
def test_login_is_rate_limited(api, user_a, settings_override=None):
    """Brute force protection: repeated bad passwords must eventually 429."""
    from django.core.cache import cache
    cache.clear()

    codes = []
    for _ in range(15):
        resp = api.post('/api/token/', {'username': 'alice', 'password': 'wrong'}, format='json')
        codes.append(resp.status_code)

    assert 429 in codes, f"no throttling observed: {codes}"
    cache.clear()
