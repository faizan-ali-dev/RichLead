import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from django.contrib import admin

from admin_dashboard.models import AnalyticsEvent, LoginActivity, SocialLink
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
