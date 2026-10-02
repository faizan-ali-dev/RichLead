import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from integrations.models import APIIntegration
from integrations.apollo_service import fetch_apollo_leads
from integrations.hunter_service import fetch_hunter_leads
from leads.models import Lead


TEST_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'richlead-cache-integration-tests',
    },
}


@pytest.mark.django_db(transaction=True)
@override_settings(
    CACHES=TEST_CACHE,
    CACHE_ENABLED=True,
    CACHE_DASHBOARD_STATS_TTL=20,
)
def test_dashboard_cache_is_tenant_scoped_and_invalidated_after_lead_write(user_a, monkeypatch):
    from leads.views import _build_dashboard_stats

    cache.clear()
    compute_calls = []
    original_compute = _build_dashboard_stats

    def counted_compute(user, *, today=None):
        compute_calls.append(user.pk)
        return original_compute(user, today=today)

    monkeypatch.setattr('leads.views._build_dashboard_stats', counted_compute)
    client = APIClient()
    client.force_authenticate(user=user_a)

    first = client.get('/api/dashboard/stats/')
    second = client.get('/api/dashboard/stats/')
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert compute_calls == [user_a.pk]

    Lead.objects.create(
        user=user_a,
        name='Fresh lead',
        company='Fresh Co',
        niche='SaaS',
        email='fresh@fresh-co.test',
    )
    updated = client.get('/api/dashboard/stats/')
    assert updated.status_code == 200
    assert updated.json()['leads_discovered'] == 1
    assert compute_calls == [user_a.pk, user_a.pk]


@pytest.mark.django_db
@override_settings(
    CACHES=TEST_CACHE,
    CACHE_ENABLED=True,
    CACHE_APOLLO_PREVIEW_TTL=120,
)
def test_apollo_company_preview_cache_is_scoped_by_user_and_key(user_a, user_b, monkeypatch):
    cache.clear()
    APIIntegration.objects.create(user=user_a, provider='apollo', encrypted_api_key='encrypted-a')
    APIIntegration.objects.create(user=user_b, provider='apollo', encrypted_api_key='encrypted-b')
    monkeypatch.setattr(APIIntegration, 'get_api_key', lambda _self: 'same-test-key')
    calls = []

    def fake_apollo_post(api_key, endpoint, *, params=None, json=None):
        calls.append((api_key, endpoint))
        return {
            'organizations': [{'id': 'org-1', 'name': 'Example Co', 'website_url': 'example.test'}],
            'pagination': {'total_entries': 1},
        }

    monkeypatch.setattr('integrations.apollo_service._apollo_post', fake_apollo_post)
    params = {'lead_type': 'companies', 'company_name': 'Example Co', 'count': 1}

    first = fetch_apollo_leads(user_a, params)
    repeated = fetch_apollo_leads(user_a, params)
    other_tenant = fetch_apollo_leads(user_b, params)

    assert first['companies'] == repeated['companies'] == other_tenant['companies']
    assert len(calls) == 2
    assert Lead.objects.filter(user__in=[user_a, user_b]).count() == 0


@pytest.mark.django_db
@override_settings(
    CACHES=TEST_CACHE,
    CACHE_ENABLED=True,
    CACHE_HUNTER_PREVIEW_TTL=120,
)
def test_hunter_company_preview_uses_cache_but_does_not_cache_contact_search(user_a, monkeypatch):
    cache.clear()
    APIIntegration.objects.create(user=user_a, provider='hunter', encrypted_api_key='encrypted-a')
    monkeypatch.setattr(APIIntegration, 'get_api_key', lambda _self: 'hunter-test-key')
    calls = []

    def fake_hunter_request(api_key, endpoint, **kwargs):
        calls.append((api_key, endpoint))
        return {
            'data': [{'domain': 'example.test', 'organization': 'Example Co', 'emails_count': {'total': 3}}],
            'meta': {'results': 1},
        }

    monkeypatch.setattr('integrations.hunter_service._hunter_request', fake_hunter_request)
    params = {'lead_type': 'companies', 'keywords': 'SaaS', 'location': 'US'}

    first = fetch_hunter_leads(user_a, params)
    repeated = fetch_hunter_leads(user_a, params)

    assert first['preview_only'] is repeated['preview_only'] is True
    assert first['companies'] == repeated['companies']
    assert len(calls) == 1
    assert Lead.objects.filter(user=user_a).count() == 0


@pytest.mark.django_db
@override_settings(
    CACHES=TEST_CACHE,
    CACHE_ENABLED=True,
    CACHE_PROVIDER_METADATA_TTL=86400,
)
def test_llm_provider_metadata_is_cached_but_user_configuration_stays_live(user_a, monkeypatch):
    cache.clear()
    catalog_calls = []
    catalog = [{'provider': 'openai', 'label': 'OpenAI', 'models': []}]

    def build_catalog():
        catalog_calls.append(True)
        return catalog

    monkeypatch.setattr('ai_engine.llm_views.providers.catalog', build_catalog)
    client = APIClient()
    client.force_authenticate(user=user_a)

    first = client.get('/api/ai/llm/catalog/')
    integration = APIIntegration.objects.create(
        user=user_a,
        provider='openai',
        encrypted_api_key='encrypted-openai',
        model='gpt-test',
    )
    second = client.get('/api/ai/llm/catalog/')

    assert first.status_code == second.status_code == 200
    assert first.json()['providers'] == second.json()['providers'] == catalog
    assert second.json()['configured']['openai']['id'] == integration.id
    assert len(catalog_calls) == 1
