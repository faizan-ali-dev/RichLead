from ipaddress import ip_address
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import Client
from django.test import override_settings
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from inbox.models import EmailMessage
from integrations.models import APIIntegration, EmailAccount, OAuthState, SuppressionEntry
from integrations.network import UnsafeMailServer, public_mail_server_addresses
from integrations.oauth_state import consume_state, issue_state
from users.admin import UserAdmin

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user('secure-user', 'secure@example.test', 'Good-password-429!', email_verified=True)


@pytest.fixture
def authenticated_client(user):
    client = APIClient()
    response = client.post('/api/token/', {'username': user.username, 'password': 'Good-password-429!'}, format='json')
    assert response.status_code == 200
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return client


def _lead(owner, email='lead@example.test'):
    from leads.models import Lead
    return Lead.objects.create(user=owner, name='Prospect', company='Example', niche='SaaS', email=email)


@override_settings(
    PASSWORD_RESET_EMAIL_ENABLED=True,
    MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}},
    PASSWORD_RESET_SENDER_ADDRESS='verify@example.test',
    PASSWORD_RESET_FROM_NAME='Rich Lead',
)
def test_public_signup_cannot_grant_staff_or_superuser(db):
    mail.outbox.clear()
    response = APIClient().post('/api/users/register/', {
        'full_name': 'Unprivileged User', 'email': 'u@example.test', 'password': 'Good-password-429!',
        'is_active': False, 'is_staff': True, 'is_superuser': True,
    }, format='json')
    assert response.status_code == 201
    new_user = User.objects.get(email='u@example.test')
    assert new_user.username != 'unprivileged'
    assert new_user.get_full_name() == 'Unprivileged User'
    assert new_user.is_active and not new_user.is_staff and not new_user.is_superuser
    assert not new_user.email_verified
    assert len(mail.outbox) == 1


def test_other_user_lead_is_hidden_from_detail_edit_and_delete(authenticated_client, user):
    other = User.objects.create_user('other', 'other@example.test', 'Good-password-429!')
    lead = _lead(other)
    url = f'/api/leads/{lead.pk}/'
    assert authenticated_client.get(url).status_code == 404
    assert authenticated_client.patch(url, {'name': 'hijacked'}, format='json').status_code == 404
    assert authenticated_client.delete(url).status_code == 404
    lead.refresh_from_db()
    assert lead.name == 'Prospect'


def test_other_users_sender_keys_suppressions_prompts_and_inbox_are_isolated(authenticated_client, user):
    from ai_engine.models import PromptTemplate
    other = User.objects.create_user('tenant-b', 'tenant-b@example.test', 'Good-password-429!')
    other_lead = _lead(other, 'tenant-b-lead@example.test')
    account = EmailAccount.objects.create(user=other, email_address='tenant-b@example.test')
    integration = APIIntegration(user=other, provider='apollo', encrypted_api_key='')
    integration.set_api_key('test-only-key')
    integration.save()
    suppression = SuppressionEntry.objects.create(user=other, email='blocked@example.test')
    prompt = PromptTemplate.objects.create(user=other, name='Private prompt')
    EmailMessage.objects.create(
        user=other, lead=other_lead, account=account, message_id='other-tenant-message',
        from_email=other_lead.email, to_email=other.email, received_at=timezone.now(),
        body_text='private tenant message',
    )
    for route, obj in (
        ('/api/integrations/email-accounts/', account),
        ('/api/integrations/api-keys/', integration),
        ('/api/integrations/suppression/', suppression),
        ('/api/ai/prompts/', prompt),
    ):
        assert authenticated_client.get(f'{route}{obj.pk}/').status_code == 404
    inbox_response = authenticated_client.get('/api/inbox/')
    assert inbox_response.status_code == 200
    assert 'private tenant message' not in str(inbox_response.data)


def test_deactivated_user_cannot_log_in_or_use_existing_tokens(authenticated_client, user):
    token_pair = APIClient().post(
        '/api/token/', {'username': user.username, 'password': 'Good-password-429!'}, format='json',
    ).data
    user.is_active = False
    user.save(update_fields=['is_active'])
    assert authenticated_client.get('/api/users/settings/').status_code == 401
    anonymous = APIClient()
    assert anonymous.post('/api/token/', {'username': user.username, 'password': 'Good-password-429!'}, format='json').status_code == 401
    assert anonymous.post('/api/token/refresh/', {'refresh': token_pair['refresh']}, format='json').status_code == 401


def test_custom_user_admin_exposes_account_status_without_password_hash():
    model_admin = admin.site._registry[User]
    assert isinstance(model_admin, UserAdmin)
    configured_fields = [field for _, section in model_admin.fieldsets for field in section['fields']]
    assert 'password' not in configured_fields
    assert 'is_active' in configured_fields
    assert not model_admin.has_add_permission(None)


def test_staff_can_suspend_account_in_admin_without_password_hash(user):
    staff = User.objects.create_superuser('operator', 'operator@example.test', 'Operator-password-429!')
    browser = Client()
    browser.force_login(staff)
    change_url = f'/admin/users/user/{user.pk}/change/'
    page = browser.get(change_url)
    assert page.status_code == 200
    assert b'name="is_active"' in page.content
    assert user.password.encode() not in page.content
    response = browser.post(change_url, {'is_active': '', '_save': 'Save'})
    assert response.status_code == 302
    user.refresh_from_db()
    assert not user.is_active


@pytest.mark.parametrize('host', [
    '127.0.0.1', '10.0.0.1', '172.16.0.1', '192.168.1.1', '169.254.169.254',
    '0.0.0.0', '224.0.0.1', '::1', 'fc00::1', 'fe80::1', '2001:db8::1',
    'localhost', 'mail.example.test/path', 'user@mail.example.test',
])
def test_mail_server_rejects_private_or_malformed_targets(host):
    with pytest.raises(UnsafeMailServer):
        public_mail_server_addresses(host, 587)


def test_mail_server_rejects_mixed_public_and_private_dns_answers():
    private = (2, 1, 6, '', ('10.0.0.5', 587))
    public = (2, 1, 6, '', ('8.8.8.8', 587))
    with patch('integrations.network.socket.getaddrinfo', return_value=[public, private]):
        with pytest.raises(UnsafeMailServer):
            public_mail_server_addresses('mail.example.test', 587)


def test_public_mail_hosts_are_pinned_to_the_validated_ip():
    public = (2, 1, 6, '', ('8.8.8.8', 587))
    with patch('integrations.network.socket.getaddrinfo', return_value=[public]) as lookup:
        hostname, addresses = public_mail_server_addresses('mail.example.test', 587)
    assert hostname == 'mail.example.test'
    assert ip_address(addresses[0][3][0]).is_global
    lookup.assert_called_once()


def test_mail_socket_connects_directly_to_validated_dns_address():
    from integrations.network import open_public_mail_socket
    public = (2, 1, 6, '', ('8.8.8.8', 587))
    sock = Mock()
    with patch('integrations.network.socket.getaddrinfo', return_value=[public]), \
         patch('integrations.network.socket.socket', return_value=sock):
        hostname, opened = open_public_mail_socket('mail.example.test', 587)
    assert hostname == 'mail.example.test' and opened is sock
    sock.connect.assert_called_once_with(('8.8.8.8', 587))


def test_saved_smtp_hostname_is_rechecked_after_dns_changes_to_private(user, monkeypatch):
    from integrations.services import send_outreach_email
    lead = _lead(user)
    account = EmailAccount.objects.create(
        user=user, email_address='sender@example.test', auth_type='smtp',
        smtp_host='mail.example.test', smtp_port=587, is_connected=True,
    )
    account.set_password('test-only-password')
    account.save(update_fields=['encrypted_password'])
    private = (2, 1, 6, '', ('169.254.169.254', 587))
    with patch('integrations.network.socket.getaddrinfo', return_value=[private]), \
         patch('integrations.services.connect_smtp') as connector:
        result = send_outreach_email(lead.pk, user, 'test-only body', account_id=account.pk)
    connector.assert_not_called()
    assert not result['success']


def test_smtp_and_imap_account_api_rejects_private_hosts(authenticated_client):
    for field in ('smtp_host', 'imap_host'):
        response = authenticated_client.post('/api/integrations/email-accounts/', {
            'email_address': 'person@example.test', 'auth_type': 'smtp', field: '127.0.0.1',
            'password': 'local-test-password',
        }, format='json')
        assert response.status_code == 400
    assert EmailAccount.objects.count() == 0


def test_inbox_serializer_removes_scripts_event_handlers_and_unsafe_links(user, authenticated_client):
    from leads.models import Lead
    lead = _lead(user)
    EmailMessage.objects.create(
        user=user, lead=lead, message_id='malicious-html', from_email=lead.email,
        to_email=user.email, received_at=timezone.now(),
        body_html='<p onclick="steal()">Hello <strong>friend</strong></p><script>steal()</script>'
                  '<img src=x onerror="steal()"><a href="javascript:steal()">open</a>',
    )
    response = authenticated_client.get('/api/inbox/')
    assert response.status_code == 200
    html = response.data[0]['messages'][0]['body_html']
    assert '<strong>friend</strong>' in html
    assert '<script' not in html and 'onclick=' not in html and 'onerror=' not in html
    assert 'javascript:' not in html and '<img' not in html


@pytest.mark.parametrize('provider', ['google', 'microsoft'])
def test_oauth_state_requires_the_initiating_browser_and_is_single_use(user, provider):
    first_browser = 'first-browser-random-cookie-value'
    state = issue_state(user.pk, provider, first_browser)
    assert consume_state(state, provider, 'other-browser-cookie') is None
    accepted = consume_state(state, provider, first_browser)
    assert accepted and accepted[0] == user.pk and accepted[1]
    assert consume_state(state, provider, first_browser) is None


def test_oauth_init_issues_http_only_browser_cookie_and_callback_rejects_link_substitution(user):
    client_a = APIClient()
    client_a.force_authenticate(user=user)
    init = client_a.get('/api/integrations/oauth/google/init/')
    assert init.status_code == 200
    cookie = init.cookies['richlead_oauth_binding']
    assert cookie['httponly'] and cookie['samesite'] == 'Lax'
    state = parse_qs(urlparse(init.data['url']).query)['state'][0]

    client_b = APIClient()
    with patch('integrations.oauth_views.requests.post') as provider_post:
        callback = client_b.get('/api/integrations/oauth/google/callback/', {'state': state, 'code': 'mock-code'})
    provider_post.assert_not_called()
    assert 'invalid_state' in callback['Location']
    assert not EmailAccount.objects.filter(user=user).exists()


def test_oauth_init_callback_same_browser_succeeds_without_any_live_provider(user):
    client = APIClient()
    client.force_authenticate(user=user)
    init = client.get('/api/integrations/oauth/google/init/')
    state = parse_qs(urlparse(init.data['url']).query)['state'][0]
    token_response = Mock(status_code=200)
    token_response.json.return_value = {'access_token': 'mock-access', 'refresh_token': 'mock-refresh'}
    profile_response = Mock(status_code=200)
    profile_response.json.return_value = {'email': 'mailbox@example.test'}
    with patch('integrations.oauth_views.requests.post', return_value=token_response), \
         patch('integrations.oauth_views.requests.get', return_value=profile_response):
        callback = client.get('/api/integrations/oauth/google/callback/', {'state': state, 'code': 'mock-code'})
    assert 'google_connected' in callback['Location']
    assert EmailAccount.objects.filter(user=user, email_address='mailbox@example.test').exists()
