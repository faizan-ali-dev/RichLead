import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client, RequestFactory

from admin_dashboard.models import PlatformTeamMember
from users.admin import _set_platform_read_only_permissions

User = get_user_model()


@pytest.mark.django_db
def test_superuser_can_create_separate_read_only_team_account():
    owner = User.objects.create_superuser(
        username='platform-owner',
        email='owner@example.test',
        password='Strong!Owner2026',
    )
    client = Client()
    client.force_login(owner)

    response = client.post(reverse('admin:admin_dashboard_platformteammember_add'), {
        'email': 'viewer@example.test',
        'full_name': 'Taylor Viewer',
        'password1': 'Distinct!Viewer2026',
        'password2': 'Distinct!Viewer2026',
        'access_level': 'read_only',
    })

    assert response.status_code == 302
    member = PlatformTeamMember.objects.get(user__email='viewer@example.test')
    member.user.refresh_from_db()
    assert member.access_level == PlatformTeamMember.ACCESS_LEVEL_READ_ONLY
    assert member.user.is_staff is True
    assert member.user.is_superuser is False
    assert member.user.check_password('Distinct!Viewer2026')
    assert member.user.has_perm('users.view_user')
    assert member.user.has_perm('users.change_user') is False
    assert member.user.has_perm('admin_dashboard.view_sociallink')
    assert member.user.has_perm('admin_dashboard.change_sociallink') is False
    assert PlatformTeamMember.objects.filter(
        user=owner,
        access_level=PlatformTeamMember.ACCESS_LEVEL_SUPER_ADMIN,
    ).exists()


@pytest.mark.django_db
def test_superuser_can_create_customer_account_from_django_admin():
    owner = User.objects.create_superuser(
        username='platform-owner', email='owner@example.test', password='Strong!Owner2026',
    )
    client = Client()
    client.force_login(owner)

    response = client.post(reverse('admin:users_user_add'), {
        'email': 'new-customer@example.test',
        'full_name': 'Morgan New Customer',
        'nickname': 'Morgan',
        'password1': 'Unique!Customer2026',
        'password2': 'Unique!Customer2026',
        'email_verified': 'on',
        'is_active': 'on',
    })

    assert response.status_code == 302
    customer = User.objects.get(email='new-customer@example.test')
    assert customer.get_full_name() == 'Morgan New Customer'
    assert customer.nickname == 'Morgan'
    assert customer.email_verified is True
    assert customer.is_active is True
    assert customer.is_staff is False
    assert customer.is_superuser is False
    assert customer.check_password('Unique!Customer2026')


@pytest.mark.django_db
def test_superuser_can_create_and_reassign_a_team_super_admin_role():
    owner = User.objects.create_superuser(
        username='platform-owner', email='owner@example.test', password='Strong!Owner2026',
    )
    client = Client()
    client.force_login(owner)

    created = client.post(reverse('admin:admin_dashboard_platformteammember_add'), {
        'email': 'new-admin@example.test',
        'full_name': 'Jamie New Admin',
        'password1': 'Unique!Team2026',
        'password2': 'Unique!Team2026',
        'access_level': 'super_admin',
    })
    assert created.status_code == 302
    member = PlatformTeamMember.objects.get(user__email='new-admin@example.test')
    member.user.refresh_from_db()
    assert member.access_level == PlatformTeamMember.ACCESS_LEVEL_SUPER_ADMIN
    assert member.user.is_staff is True
    assert member.user.is_superuser is True
    assert member.user.check_password('Unique!Team2026')


@pytest.mark.django_db
def test_team_role_changes_sync_django_permissions_and_prevent_last_admin_lockout():
    owner = User.objects.create_superuser(
        username='platform-owner', email='owner@example.test', password='Strong!Owner2026',
    )
    team_user = User.objects.create_user(
        username='viewer@example.test', email='viewer@example.test', password='Distinct!Viewer2026', is_staff=True,
    )
    _set_platform_read_only_permissions(team_user)
    member = PlatformTeamMember.objects.create(
        user=team_user,
        access_level=PlatformTeamMember.ACCESS_LEVEL_READ_ONLY,
        created_by=owner,
    )
    client = Client()
    client.force_login(owner)

    promoted = client.post(reverse('admin:admin_dashboard_platformteammember_change', args=(member.pk,)), {
        'full_name': 'Taylor Admin',
        'access_level': 'super_admin',
        'is_active': 'on',
    })
    assert promoted.status_code == 302
    team_user.refresh_from_db()
    member.refresh_from_db()
    assert member.access_level == PlatformTeamMember.ACCESS_LEVEL_SUPER_ADMIN
    assert team_user.is_superuser is True

    demoted = client.post(reverse('admin:admin_dashboard_platformteammember_change', args=(member.pk,)), {
        'full_name': 'Taylor Viewer',
        'access_level': 'read_only',
        'is_active': 'on',
    })
    assert demoted.status_code == 302
    team_user.refresh_from_db()
    member.refresh_from_db()
    assert member.access_level == PlatformTeamMember.ACCESS_LEVEL_READ_ONLY
    assert team_user.is_superuser is False
    assert team_user.has_perm('users.view_user')
    assert team_user.has_perm('users.change_user') is False

    owner_member = PlatformTeamMember.objects.get(user=owner)
    self_edit = client.post(reverse('admin:admin_dashboard_platformteammember_change', args=(owner_member.pk,)), {
        'full_name': 'Platform Owner',
        'access_level': 'read_only',
        'is_active': 'on',
    })
    assert self_edit.status_code == 200
    owner_member.refresh_from_db()
    assert owner_member.access_level == PlatformTeamMember.ACCESS_LEVEL_SUPER_ADMIN


@pytest.mark.django_db
def test_read_only_team_member_can_view_admin_but_cannot_change_records(api):
    owner = User.objects.create_superuser(
        username='platform-owner',
        email='owner@example.test',
        password='Strong!Owner2026',
    )
    team_user = User.objects.create_user(
        username='viewer@example.test',
        email='viewer@example.test',
        password='Distinct!Viewer2026',
        is_staff=True,
        email_verified=True,
    )
    _set_platform_read_only_permissions(team_user)
    PlatformTeamMember.objects.create(
        user=team_user,
        access_level=PlatformTeamMember.ACCESS_LEVEL_READ_ONLY,
        created_by=owner,
    )

    client = Client()
    client.force_login(team_user)

    assert client.get('/admin/').status_code == 200
    assert client.get(reverse('admin:users_user_changelist')).status_code == 200
    assert client.get(reverse('admin:admin_dashboard_sociallink_changelist')).status_code == 200
    assert client.get(reverse('admin:admin_dashboard_platformteammember_changelist')).status_code == 200
    assert client.get(reverse('admin:admin_dashboard_sociallink_add')).status_code == 403
    assert client.get(reverse('admin:admin_dashboard_platformteammember_add')).status_code == 403
    assert client.get(reverse('admin:users_user_add')).status_code == 403

    token_response = api.post('/api/token/', {
        'username': team_user.username,
        'password': 'Distinct!Viewer2026',
    }, format='json')
    assert token_response.status_code == 401


@pytest.mark.django_db
def test_suspending_team_member_disables_admin_login():
    owner = User.objects.create_superuser(
        username='platform-owner',
        email='owner@example.test',
        password='Strong!Owner2026',
    )
    team_user = User.objects.create_user(
        username='viewer@example.test',
        email='viewer@example.test',
        password='Distinct!Viewer2026',
        is_staff=True,
    )
    member = PlatformTeamMember.objects.create(
        user=team_user,
        access_level=PlatformTeamMember.ACCESS_LEVEL_READ_ONLY,
        created_by=owner,
    )
    member.is_active = False
    request = RequestFactory().post('/admin/')
    request.user = owner
    admin.site._registry[PlatformTeamMember].save_model(request, member, form=None, change=True)

    team_user.refresh_from_db()
    assert team_user.is_active is False
    assert team_user.is_staff is True
    assert team_user.is_superuser is False


@pytest.mark.django_db
def test_customer_admin_api_never_lists_or_updates_platform_team(api, user_a):
    owner = User.objects.create_superuser(
        username='platform-owner',
        email='owner@example.test',
        password='Strong!Owner2026',
    )
    team_user = User.objects.create_user(
        username='viewer@example.test',
        email='viewer@example.test',
        password='Distinct!Viewer2026',
        is_staff=True,
    )
    PlatformTeamMember.objects.create(
        user=team_user,
        access_level=PlatformTeamMember.ACCESS_LEVEL_READ_ONLY,
        created_by=owner,
    )
    api.force_authenticate(user=owner)

    listed = api.get('/api/admin-dashboard/users/')
    assert listed.status_code == 200
    assert listed.data['count'] == 1
    assert listed.data['results'][0]['email'] == user_a.email

    updated = api.patch(f'/api/admin-dashboard/users/{team_user.pk}/', {'is_active': False}, format='json')
    assert updated.status_code == 404
