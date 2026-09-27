from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.http import HttpResponseRedirect
from django.conf import settings
from .models import EmailAccount
from .oauth_state import issue_state, consume_state, code_challenge_for
import urllib.parse
import logging
import requests
import json
import base64
import os
import secrets

logger = logging.getLogger(__name__)

FRONTEND_SENDERS_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000').rstrip('/') + '/senders'
BACKEND_BASE_URL = os.getenv('BACKEND_URL', 'http://localhost:8000').rstrip('/')
GOOGLE_REDIRECT_URI = f'{BACKEND_BASE_URL}/api/integrations/oauth/google/callback/'
MICROSOFT_REDIRECT_URI = f'{BACKEND_BASE_URL}/api/integrations/oauth/microsoft/callback/'
OAUTH_BINDING_COOKIE = 'richlead_oauth_binding'


def _oauth_binding(request, provider):
    binding = request.COOKIES.get(OAUTH_BINDING_COOKIE) or secrets.token_urlsafe(32)
    state = issue_state(request.user.id, provider, binding)
    return state, binding


def _binding_cookie(response, binding, provider, request):
    response.set_cookie(
        OAUTH_BINDING_COOKIE,
        binding,
        max_age=600,
        httponly=True,
        secure=request.is_secure(),
        samesite='Lax',
        path=f'/api/integrations/oauth/{provider}/callback/',
    )
    return response

# --- GOOGLE OAUTH ---
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def google_oauth_init(request):
    """
    Initializes the Google OAuth flow.
    """
    # Opaque single-use state stored server-side. Never encode identity into it.
    state, binding = _oauth_binding(request, 'google')
    from .models import OAuthState
    verifier = OAuthState.objects.get(state=state).code_verifier

    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', 'DUMMY_GOOGLE_CLIENT_ID')
    redirect_uri = GOOGLE_REDIRECT_URI

    scope = "https://www.googleapis.com/auth/userinfo.email https://mail.google.com/"

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': scope,
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state,
        'code_challenge': code_challenge_for(verifier),
        'code_challenge_method': 'S256',
    }

    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return _binding_cookie(Response({"url": url}), binding, 'google', request)

@api_view(['GET'])
@permission_classes([AllowAny])
def google_oauth_callback(request):
    # Public by necessity: Google redirects the user's browser here with no bearer
    # token. Authorisation comes from the single-use signed state, not a session.
    code = request.GET.get('code')
    state = request.GET.get('state')
    
    frontend_url = FRONTEND_SENDERS_URL

    if not code:
        return HttpResponseRedirect(f"{frontend_url}?error=auth_denied")

    consumed = consume_state(state, 'google', request.COOKIES.get(OAUTH_BINDING_COOKIE))
    if consumed is None:
        logger.warning("Rejected Google OAuth callback with invalid or replayed state")
        return HttpResponseRedirect(f"{frontend_url}?error=invalid_state")
    user_id, verifier = consumed
    from django.contrib.auth import get_user_model
    if not get_user_model().objects.filter(pk=user_id, is_active=True).exists():
        return HttpResponseRedirect(f"{frontend_url}?error=account_inactive")

    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', 'DUMMY_GOOGLE_CLIENT_ID')
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', 'DUMMY_SECRET')
    redirect_uri = GOOGLE_REDIRECT_URI

    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
        'code_verifier': verifier or '',
    }

    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        # In MVP, if the client ID is dummy, this will fail. We'll handle it nicely.
        return HttpResponseRedirect(f"{frontend_url}?error=invalid_client_credentials")
        
    tokens = response.json()
    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')
    
    # Get user's email address
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {'Authorization': f'Bearer {access_token}'}
    userinfo_resp = requests.get(userinfo_url, headers=headers)
    
    if userinfo_resp.status_code != 200:
        return HttpResponseRedirect(f"{frontend_url}?error=failed_to_get_email")
        
    userinfo = userinfo_resp.json()
    email_address = userinfo.get('email')
    
    # Save EmailAccount
    account, created = EmailAccount.objects.get_or_create(
        user_id=user_id,
        email_address=email_address,
        defaults={'provider': 'google', 'auth_type': 'oauth_google'}
    )
    
    # Update tokens
    account.set_oauth_tokens(access_token, refresh_token)
    account.is_connected = True
    account.save()
    
    return HttpResponseRedirect(f"{frontend_url}?success=google_connected")


# --- MICROSOFT OAUTH ---
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def microsoft_oauth_init(request):
    """
    Initializes the Microsoft Azure AD OAuth flow (supports common / consumers / specific tenant).
    """
    state, binding = _oauth_binding(request, 'microsoft')
    from .models import OAuthState
    verifier = OAuthState.objects.get(state=state).code_verifier

    client_id = getattr(settings, 'MICROSOFT_CLIENT_ID', 'DUMMY_MS_CLIENT_ID')
    redirect_uri = MICROSOFT_REDIRECT_URI

    scope = "openid profile email offline_access User.Read Mail.Send Mail.ReadWrite"

    prompt = request.GET.get('prompt', 'login')
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': scope,
        'state': state,
        'prompt': prompt,
        'response_mode': 'query',
        'code_challenge': code_challenge_for(verifier),
        'code_challenge_method': 'S256',
    }

    tenant_id = os.getenv('MICROSOFT_TENANT_ID', 'common')
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize?" + urllib.parse.urlencode(params)
    return _binding_cookie(Response({"url": url}), binding, 'microsoft', request)

@api_view(['GET'])
@permission_classes([AllowAny])
def microsoft_oauth_callback(request):
    # Public by necessity, same as the Google callback: the state parameter carries
    # the trust, since the provider redirect cannot include credentials.
    logger.debug("Microsoft OAuth callback received")
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    error_description = request.GET.get('error_description') or request.GET.get('error_subcode') or ''
    
    frontend_url = FRONTEND_SENDERS_URL

    if error or not code:
        err_msg = error_description or error or "auth_denied"
        logger.warning("Microsoft OAuth callback error: %s", err_msg)
        encoded_err = urllib.parse.quote(err_msg)
        return HttpResponseRedirect(f"{frontend_url}?error={encoded_err}")

    consumed = consume_state(state, 'microsoft', request.COOKIES.get(OAUTH_BINDING_COOKIE))
    if consumed is None:
        logger.warning("Rejected Microsoft OAuth callback with invalid or replayed state")
        return HttpResponseRedirect(f"{frontend_url}?error=invalid_state")
    user_id, verifier = consumed
    from django.contrib.auth import get_user_model
    if not get_user_model().objects.filter(pk=user_id, is_active=True).exists():
        return HttpResponseRedirect(f"{frontend_url}?error=account_inactive")

    client_id = getattr(settings, 'MICROSOFT_CLIENT_ID', 'DUMMY_MS_CLIENT_ID')
    client_secret = getattr(settings, 'MICROSOFT_CLIENT_SECRET', 'DUMMY_SECRET')
    redirect_uri = MICROSOFT_REDIRECT_URI

    tenant_id = os.getenv('MICROSOFT_TENANT_ID', 'common')
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        'client_id': client_id,
        'scope': 'openid profile email offline_access User.Read Mail.Send Mail.ReadWrite',
        'code': code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
        'client_secret': client_secret,
        'code_verifier': verifier or '',
    }

    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        err_body = response.text
        logger.error("Microsoft token exchange failed with status %s", response.status_code)
        try:
            err_json = response.json()
            err_msg = err_json.get('error_description') or err_json.get('error') or err_body
        except Exception:
            err_msg = err_body
        encoded_err = urllib.parse.quote(f"token_error: {err_msg}")
        return HttpResponseRedirect(f"{frontend_url}?error={encoded_err}")
        
    tokens = response.json()
    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')
    
    # Get user email
    graph_url = "https://graph.microsoft.com/v1.0/me"
    headers = {'Authorization': f'Bearer {access_token}'}
    graph_resp = requests.get(graph_url, headers=headers)
    
    email_address = None
    if graph_resp.status_code == 200:
        graph_data = graph_resp.json()
        logger.debug("Microsoft Graph profile retrieved")
        mail_val = graph_data.get('mail')
        upn_val = graph_data.get('userPrincipalName')
        if mail_val and any(d in mail_val.lower() for d in ['@outlook.', '@hotmail.', '@live.']):
            email_address = mail_val
        elif upn_val and any(d in upn_val.lower() for d in ['@outlook.', '@hotmail.', '@live.']):
            email_address = upn_val
        else:
            email_address = mail_val or upn_val
    else:
        logger.warning("Microsoft Graph lookup failed with status %s", graph_resp.status_code)
        
    # Fallback or check id_token payload
    if (not email_address or '@' not in str(email_address) or '@gmail.com' in str(email_address).lower()) and 'id_token' in tokens:
        try:
            id_payload_part = tokens['id_token'].split('.')[1]
            padded = id_payload_part + '=' * ((4 - len(id_payload_part) % 4) % 4)
            id_payload = json.loads(base64.urlsafe_b64decode(padded).decode())
            logger.debug("Decoded Microsoft ID token claims")
            id_email = id_payload.get('email')
            id_pref = id_payload.get('preferred_username')
            if id_email and any(d in id_email.lower() for d in ['@outlook.', '@hotmail.', '@live.']):
                email_address = id_email
            elif id_pref and any(d in id_pref.lower() for d in ['@outlook.', '@hotmail.', '@live.']):
                email_address = id_pref
            elif not email_address:
                email_address = id_email or id_pref or email_address
        except Exception as id_err:
            logger.warning("Could not decode Microsoft ID token: %s", id_err)
            
    if not email_address:
        encoded_err = urllib.parse.quote("Could not retrieve email address from Microsoft account.")
        return HttpResponseRedirect(f"{frontend_url}?error={encoded_err}")
    
    # Save EmailAccount
    account, created = EmailAccount.objects.get_or_create(
        user_id=user_id,
        email_address=email_address,
        defaults={'provider': 'outlook', 'auth_type': 'oauth_microsoft'}
    )
    
    account.set_oauth_tokens(access_token, refresh_token)
    account.is_connected = True
    account.save()
    
    return HttpResponseRedirect(f"{frontend_url}?success=microsoft_connected")

