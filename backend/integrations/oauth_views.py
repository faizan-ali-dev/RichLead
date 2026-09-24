from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponseRedirect
from django.conf import settings
from .models import EmailAccount
import urllib.parse
import requests
import json
import base64
import os

# --- GOOGLE OAUTH ---
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def google_oauth_init(request):
    """
    Initializes the Google OAuth flow.
    """
    # Create state token that contains user ID to identify them in the callback
    state_data = json.dumps({"user_id": request.user.id})
    state = base64.urlsafe_b64encode(state_data.encode()).decode()
    
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', 'DUMMY_GOOGLE_CLIENT_ID')
    redirect_uri = 'http://localhost:8000/api/integrations/oauth/google/callback/'
    
    scope = "https://www.googleapis.com/auth/userinfo.email https://mail.google.com/"
    
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': scope,
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state
    }
    
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return Response({"url": url})

@api_view(['GET'])
def google_oauth_callback(request):
    code = request.GET.get('code')
    state = request.GET.get('state')
    
    frontend_url = 'http://localhost:3000/senders'
    
    if not code:
        return HttpResponseRedirect(f"{frontend_url}?error=auth_denied")
        
    try:
        # Decode state to get user ID
        state_data = json.loads(base64.urlsafe_b64decode(state.encode()).decode())
        user_id = state_data.get('user_id')
    except Exception:
        return HttpResponseRedirect(f"{frontend_url}?error=invalid_state")
        
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', 'DUMMY_GOOGLE_CLIENT_ID')
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', 'DUMMY_SECRET')
    redirect_uri = 'http://localhost:8000/api/integrations/oauth/google/callback/'
    
    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
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
    state_data = json.dumps({"user_id": request.user.id})
    state = base64.urlsafe_b64encode(state_data.encode()).decode()
    
    client_id = getattr(settings, 'MICROSOFT_CLIENT_ID', 'DUMMY_MS_CLIENT_ID')
    redirect_uri = 'http://localhost:8000/api/integrations/oauth/microsoft/callback/'
    
    scope = "openid profile email offline_access User.Read Mail.Send Mail.ReadWrite"
    
    prompt = request.GET.get('prompt', 'login')
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': scope,
        'state': state,
        'prompt': prompt,
        'response_mode': 'query'
    }
    
    tenant_id = os.getenv('MICROSOFT_TENANT_ID', 'common')
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize?" + urllib.parse.urlencode(params)
    return Response({"url": url})

@api_view(['GET'])
def microsoft_oauth_callback(request):
    print(f"[Microsoft OAuth Callback] Received params: {dict(request.GET)}", flush=True)
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    error_description = request.GET.get('error_description') or request.GET.get('error_subcode') or ''
    
    frontend_url = 'http://localhost:3000/senders'
    
    if error or not code:
        err_msg = error_description or error or "auth_denied"
        print(f"[Microsoft OAuth Callback Error] {err_msg}", flush=True)
        encoded_err = urllib.parse.quote(err_msg)
        return HttpResponseRedirect(f"{frontend_url}?error={encoded_err}")
        
    try:
        state_data = json.loads(base64.urlsafe_b64decode(state.encode()).decode())
        user_id = state_data.get('user_id')
    except Exception as e:
        print(f"[Microsoft OAuth State Error]: {e}", flush=True)
        return HttpResponseRedirect(f"{frontend_url}?error=invalid_state")
        
    client_id = getattr(settings, 'MICROSOFT_CLIENT_ID', 'DUMMY_MS_CLIENT_ID')
    client_secret = getattr(settings, 'MICROSOFT_CLIENT_SECRET', 'DUMMY_SECRET')
    redirect_uri = 'http://localhost:8000/api/integrations/oauth/microsoft/callback/'
    
    tenant_id = os.getenv('MICROSOFT_TENANT_ID', 'common')
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        'client_id': client_id,
        'scope': 'openid profile email offline_access User.Read Mail.Send Mail.ReadWrite',
        'code': code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
        'client_secret': client_secret
    }
    
    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        err_body = response.text
        print(f"[Microsoft Token Error] Status: {response.status_code}, Body: {err_body}", flush=True)
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
        print(f"[Microsoft Graph Full Profile]: {graph_data}", flush=True)
        mail_val = graph_data.get('mail')
        upn_val = graph_data.get('userPrincipalName')
        if mail_val and any(d in mail_val.lower() for d in ['@outlook.', '@hotmail.', '@live.']):
            email_address = mail_val
        elif upn_val and any(d in upn_val.lower() for d in ['@outlook.', '@hotmail.', '@live.']):
            email_address = upn_val
        else:
            email_address = mail_val or upn_val
    else:
        print(f"[Microsoft Graph Warning] Status: {graph_resp.status_code}, Body: {graph_resp.text}", flush=True)
        
    # Fallback or check id_token payload
    if (not email_address or '@' not in str(email_address) or '@gmail.com' in str(email_address).lower()) and 'id_token' in tokens:
        try:
            id_payload_part = tokens['id_token'].split('.')[1]
            padded = id_payload_part + '=' * ((4 - len(id_payload_part) % 4) % 4)
            id_payload = json.loads(base64.urlsafe_b64decode(padded).decode())
            print(f"[Microsoft Decoded ID Token]: {id_payload}", flush=True)
            id_email = id_payload.get('email')
            id_pref = id_payload.get('preferred_username')
            if id_email and any(d in id_email.lower() for d in ['@outlook.', '@hotmail.', '@live.']):
                email_address = id_email
            elif id_pref and any(d in id_pref.lower() for d in ['@outlook.', '@hotmail.', '@live.']):
                email_address = id_pref
            elif not email_address:
                email_address = id_email or id_pref or email_address
        except Exception as id_err:
            print(f"[Microsoft ID Token Decode Error]: {id_err}", flush=True)
            
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

