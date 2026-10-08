import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from django.contrib import admin

from admin_dashboard.models import AnalyticsEvent, LoginActivity, SocialLink
from ai_engine.models import BusinessProfile
from async_jobs.models import BackgroundJob
from integrations.models import APIIntegration, EmailAccount
from leads.models import Lead

User = get_user_model()


@pytest.mark.django_db
def test_public_tracker_accepts_only_minimal_valid_events(api):
    response = api.post('/api/admin-dashboard/track/', {
        'event_type': 'page_view',
        'path': '/features',
        'session_id': '123e4567-e89b-12d3-a456-426614174000',
    }, format='json')

    assert response.status_code == 202
    assert AnalyticsEvent.objects.count() == 1
    event = AnalyticsEvent.objects.get()
    assert event.path == '/features'
    assert event.label == ''

    rejected = api.post('/api/admin-dashboard/track/', {
        'event_type': 'page_view',
        'path': '/features?email=private@example.test',
        'session_id': '123e4567-e89b-12d3-a456-426614174000',
    }, format='json')
    assert rejected.status_code == 400
    assert AnalyticsEvent.objects.count() == 1


@pytest.mark.django_db
def test_admin_dashboard_is_superuser_only(api, user_a):
    assert api.get('/api/admin-dashboard/access/').status_code == 401

    api.force_authenticate(user=user_a)
    assert api.get('/api/admin-dashboard/access/').status_code == 403
    assert api.get('/api/admin-dashboard/overview/').status_code == 403
    assert api.get('/api/admin-dashboard/users/').status_code == 403


@pytest.mark.django_db
def test_superuser_can_view_metrics_and_paginated_users(api, user_a):
    admin = User.objects.create_superuser(
        username='site-admin', email='admin@example.test', password='Strong!Pass2026', email_verified=True,
    )
    AnalyticsEvent.objects.create(
        event_type='page_view', path='/features', label='',
        session_id='123e4567-e89b-12d3-a456-426614174000',
    )
    api.force_authenticate(user=admin)

    overview = api.get('/api/admin-dashboard/overview/?days=7')
    assert overview.status_code == 200
    assert overview.data['summary']['page_views'] == 1
    assert overview.data['summary']['total_users'] == 1
    assert len(overview.data['series']) == 7

    users = api.get('/api/admin-dashboard/users/?page_size=1')
    assert users.status_code == 200
    assert users.data['count'] == 1
    assert users.data['page_size'] == 1
    assert len(users.data['results']) == 1


@pytest.mark.django_db
def test_admin_adoption_view_shows_setup_and_aggregate_usage_without_tenant_content(api, user_a, user_b):
    admin = User.objects.create_superuser(
        username='site-admin', email='admin@example.test', password='Strong!Pass2026', email_verified=True,
    )
    BusinessProfile.objects.create(
        user=user_a,
        company_name='Private Acme Company',
        what_you_do='Private product description',
        problem_you_solve='Private customer problem',
        icp_titles=['Private target title'],
    )
    BusinessProfile.objects.create(user=user_b, icp_industries=['Private target industry'])
    APIIntegration.objects.create(
        user=user_a, provider='openai', encrypted_api_key='secret-openai-ciphertext', is_primary=True,
    )
    APIIntegration.objects.create(user=user_a, provider='anthropic', encrypted_api_key='secret-anthropic-ciphertext')
    APIIntegration.objects.create(user=user_a, provider='apollo', encrypted_api_key='secret-apollo-ciphertext')
    APIIntegration.objects.create(user=user_a, provider='hunter', encrypted_api_key='secret-hunter-ciphertext')
    EmailAccount.objects.create(
        user=user_a,
        email_address='private-mailbox@example.test',
        is_connected=True,
        encrypted_password='secret-mailbox-password',
    )
    job_defaults = {
        'user': user_a,
        'request_fingerprint': 'a' * 64,
        'payload': {'query': 'private prospect search term'},
        'result': {'lead_name': 'Private lead'},
    }
    BackgroundJob.objects.create(job_type='generate_draft', status='succeeded', idempotency_key='draft-test', **job_defaults)
    BackgroundJob.objects.create(
        job_type='apollo_search', status='succeeded', idempotency_key='apollo-test', **job_defaults,
    )
    BackgroundJob.objects.create(
        job_type='hunter_search', status='failed', idempotency_key='hunter-test', **job_defaults,
    )

    api.force_authenticate(user=admin)
    users_response = api.get('/api/admin-dashboard/users/')
    overview_response = api.get('/api/admin-dashboard/overview/')

    assert users_response.status_code == 200
    adoption = next(row['adoption'] for row in users_response.data['results'] if row['id'] == user_a.pk)
    assert adoption['business_profile'] == {'status': 'complete', 'icp_configured': True}
    assert adoption['llm']['status'] == 'connected'
    assert set(adoption['llm']['providers']) == {'OpenAI', 'Anthropic'}
    assert adoption['llm']['primary_provider'] == 'OpenAI'
    assert adoption['apollo']['status'] == 'connected'
    assert adoption['apollo']['runs_30d'] == 1
    assert adoption['hunter']['status'] == 'connected'
    assert adoption['hunter']['failed_30d'] == 1
    assert adoption['ai_activity']['runs_30d'] == 1
    assert adoption['mailbox']['connected_count'] == 1

    assert overview_response.status_code == 200
    assert overview_response.data['product_adoption'] == {
        'business_profiles_complete': 1,
        'business_profiles_started': 1,
        'llm_connected_users': 1,
        'apollo_connected_users': 1,
        'hunter_connected_users': 1,
        'mailbox_connected_users': 1,
        'ai_jobs_30d': 1,
        'apollo_searches_30d': 1,
        'hunter_searches_30d': 1,
    }

    serialized = repr(users_response.data) + repr(overview_response.data)
    for private_value in (
        'Private Acme Company', 'Private product description', 'Private customer problem',
        'Private target title', 'secret-openai-ciphertext', 'secret-apollo-ciphertext',
        'Private target industry', 'secret-anthropic-ciphertext',
        'secret-hunter-ciphertext', 'private-mailbox@example.test', 'secret-mailbox-password',
        'private prospect search term', 'Private lead',
    ):
        assert private_value not in serialized


@pytest.mark.django_db
def test_admin_can_update_profile_and_access_but_not_identity_or_permissions(api, user_a):
    admin = User.objects.create_superuser(
        username='site-admin', email='admin@example.test', password='Strong!Pass2026', email_verified=True,
    )
    api.force_authenticate(user=admin)

    response = api.patch(f'/api/admin-dashboard/users/{user_a.pk}/', {
        'full_name': 'Alice Admin Updated', 'nickname': 'Alice',
        'email_verified': True, 'is_active': False,
    }, format='json')
    assert response.status_code == 200
    user_a.refresh_from_db()
    assert user_a.get_full_name() == 'Alice Admin Updated'
    assert user_a.nickname == 'Alice'
    assert user_a.email_verified is True
    assert user_a.is_active is False

    rejected = api.patch(f'/api/admin-dashboard/users/{user_a.pk}/', {
        'email': 'changed@example.test',
    }, format='json')
    assert rejected.status_code == 400
    user_a.refresh_from_db()
    assert user_a.email == 'alice@acme.test'


@pytest.mark.django_db
def test_login_activity_is_visible_to_admin_but_tenant_leads_are_not_registered(api, user_a):
    admin_user = User.objects.create_superuser(
        username='site-admin', email='admin@example.test', password='Strong!Pass2026', email_verified=True,
    )
    LoginActivity.objects.create(user=user_a)
    client = APIClient()
    client.force_login(admin_user)

    response = client.get('/admin/')

    assert response.status_code == 200
    assert b'Platform overview' in response.content
    assert b'Recent sign-ins' in response.content
    assert not admin.site.is_registered(Lead)


@pytest.mark.django_db
def test_public_social_links_return_only_enabled_safe_fields(api):
    active = SocialLink.objects.create(platform='linkedin', label='RichLead on LinkedIn', url='https://linkedin.com/company/richlead')
    SocialLink.objects.create(platform='x', url='https://x.com/richlead', is_active=False)

    response = api.get('/api/admin-dashboard/social-links/')

    assert response.status_code == 200
    assert response.data == [{
        'id': active.pk,
        'platform': 'linkedin',
        'label': 'RichLead on LinkedIn',
        'url': 'https://linkedin.com/company/richlead',
    }]


@pytest.mark.django_db
def test_social_link_admin_rejects_non_https_urls():
    social_link = SocialLink(platform='other', url='http://example.com')
    with pytest.raises(ValidationError):
        social_link.full_clean()


@pytest.mark.django_db
def test_customer_admin_api_cannot_manage_superuser_accounts(api):
    admin = User.objects.create_superuser(
        username='only-admin', email='only-admin@example.test', password='Strong!Pass2026', email_verified=True,
    )
    api.force_authenticate(user=admin)

    response = api.patch(f'/api/admin-dashboard/users/{admin.pk}/', {'is_active': False}, format='json')
    assert response.status_code == 404
    admin.refresh_from_db()
    assert admin.is_active is True
