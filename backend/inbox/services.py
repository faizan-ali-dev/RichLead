import os
import imaplib
import email
from email.header import decode_header
import requests
from django.utils import timezone
from datetime import datetime
from .models import EmailMessage
from leads.models import Lead
from integrations.models import EmailAccount

def sync_emails_for_user(user):
    """
    Syncs emails for all connected accounts of a user.
    Only saves emails that match a Lead's email address.
    """
    accounts = EmailAccount.objects.filter(user=user, is_connected=True)
    # Cache all lead emails for quick lookup
    lead_emails = set(Lead.objects.filter(user=user).values_list('email', flat=True))
    
    if not lead_emails:
        return {"success": True, "message": "No leads to sync against."}

    total_synced = 0
    for account in accounts:
        try:
            if account.auth_type == 'smtp':
                synced = _sync_imap(account, user, lead_emails)
                total_synced += synced
            elif account.auth_type == 'oauth_microsoft':
                synced = _sync_microsoft_graph(account, user, lead_emails)
                total_synced += synced
            elif account.auth_type == 'oauth_google':
                synced = _sync_google_gmail(account, user, lead_emails)
                total_synced += synced
        except Exception as e:
            print(f"Error syncing account {account.email_address}: {e}")

    return {"success": True, "synced_count": total_synced}

def _get_lead_from_email(email_addr, user, lead_emails):
    # Basic email extraction (removes "Name <email@example.com>" formatting)
    clean_email = email_addr
    if '<' in email_addr and '>' in email_addr:
        clean_email = email_addr.split('<')[1].split('>')[0]
    clean_email = clean_email.strip().lower()

    if clean_email in lead_emails:
        return Lead.objects.filter(user=user, email__iexact=clean_email).first()
    return None

def _sync_imap(account, user, lead_emails):
    """Basic IMAP sync logic."""
    if not account.imap_host:
        return 0

    password = account.get_imap_password() or account.get_password()
    if not password:
        return 0

    synced_count = 0
    try:
        mail = imaplib.IMAP4_SSL(account.imap_host, account.imap_port)
        mail.login(account.email_address, password)
        mail.select("inbox")

        # Get all emails (in a real app, use UID SEARCH SINCE date)
        status, messages = mail.search(None, "ALL")
        if status == "OK":
            for num in messages[0].split()[-20:]: # Just check last 20 for MVP
                status, data = mail.fetch(num, "(RFC822)")
                if status == "OK":
                    msg = email.message_from_bytes(data[0][1])
                    
                    # Extract headers
                    subject_bytes, encoding = decode_header(msg.get("Subject", ""))[0]
                    subject = subject_bytes.decode(encoding) if isinstance(subject_bytes, bytes) and encoding else str(subject_bytes)
                    from_email = msg.get("From", "")
                    to_email = msg.get("To", "")
                    message_id = msg.get("Message-ID", f"imap-{num.decode()}")
                    
                    date_tuple = email.utils.parsedate_tz(msg.get("Date"))
                    if date_tuple:
                        local_date = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                        received_at = timezone.make_aware(local_date)
                    else:
                        received_at = timezone.now()

                    # Match with leads
                    lead = _get_lead_from_email(from_email, user, lead_emails)
                    if lead:
                        direction = 'inbound'
                    else:
                        lead = _get_lead_from_email(to_email, user, lead_emails)
                        direction = 'outbound'

                    if lead:
                        if not EmailMessage.objects.filter(message_id=message_id).exists():
                            # Extract body
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        body = part.get_payload(decode=True).decode()
                                        break
                            else:
                                body = msg.get_payload(decode=True).decode()

                            EmailMessage.objects.create(
                                user=user,
                                lead=lead,
                                account=account,
                                message_id=message_id,
                                subject=subject,
                                from_email=from_email,
                                to_email=to_email,
                                body_text=body,
                                received_at=received_at,
                                direction=direction
                            )
                            synced_count += 1
        mail.close()
        mail.logout()
    except Exception as e:
        print(f"IMAP Error: {e}")
    return synced_count

def _sync_microsoft_graph(account, user, lead_emails):
    """Sync via MS Graph API."""
    token = account.get_access_token()
    if not token: return 0

    headers = {'Authorization': f'Bearer {token}'}
    # Fetch last 30 messages
    res = requests.get('https://graph.microsoft.com/v1.0/me/messages?$top=30', headers=headers)
    
    # Handle token refresh if expired
    if res.status_code == 401:
        refresh_token = account.get_refresh_token()
        if refresh_token:
            from django.conf import settings
            client_id = getattr(settings, 'MICROSOFT_CLIENT_ID', '')
            client_secret = getattr(settings, 'MICROSOFT_CLIENT_SECRET', '')
            tenant_id = os.getenv('MICROSOFT_TENANT_ID', 'common')
            token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
            refresh_data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }
            token_res = requests.post(token_url, data=refresh_data)
            if token_res.ok:
                token_json = token_res.json()
                new_access_token = token_json.get('access_token')
                new_refresh_token = token_json.get('refresh_token', refresh_token)
                account.set_oauth_tokens(new_access_token, new_refresh_token)
                account.save()
                headers['Authorization'] = f'Bearer {new_access_token}'
                res = requests.get('https://graph.microsoft.com/v1.0/me/messages?$top=30', headers=headers)

    if not res.ok:
        print(f"[MS Graph Sync Error] Status: {res.status_code}, Body: {res.text}")
        return 0

    synced_count = 0
    messages_list = res.json().get('value', [])

    # Also check Junk Email folder in case incoming lead reply was categorized as Junk by MS filters
    try:
        junk_res = requests.get('https://graph.microsoft.com/v1.0/me/mailFolders/junkemail/messages?$top=15', headers=headers)
        if junk_res.ok:
            existing_ids = {m.get('id') for m in messages_list if m.get('id')}
            for jm in junk_res.json().get('value', []):
                if jm.get('id') not in existing_ids:
                    messages_list.append(jm)
    except Exception as je:
        print(f"[MS Graph Junk Folder Check Error]: {je}")

    for msg in messages_list:
        message_id = msg.get('id')
        if not message_id or EmailMessage.objects.filter(message_id=message_id).exists():
            continue

        subject = msg.get('subject', '')
        from_email = msg.get('from', {}).get('emailAddress', {}).get('address', '')
        
        # Determine direction
        lead = _get_lead_from_email(from_email, user, lead_emails)
        direction = 'inbound'
        to_email = ""
        
        if not lead:
            to_recipients = msg.get('toRecipients', [])
            if to_recipients:
                to_email = to_recipients[0].get('emailAddress', {}).get('address', '')
                lead = _get_lead_from_email(to_email, user, lead_emails)
                direction = 'outbound'

        if lead:
            received_at_str = msg.get('receivedDateTime')
            received_at = datetime.fromisoformat(received_at_str.replace('Z', '+00:00')) if received_at_str else timezone.now()
            body_content = msg.get('body', {}).get('content', '')
            body_preview = msg.get('bodyPreview', '')
            body_text = body_preview if body_preview else body_content

            print(f"[MS Graph Sync] Matched Lead {lead.email} - Direction: {direction} - Subject: {subject}")
            EmailMessage.objects.create(
                user=user,
                lead=lead,
                account=account,
                message_id=message_id,
                subject=subject,
                from_email=from_email,
                to_email=to_email,
                body_text=body_text,
                body_html=body_content,
                received_at=received_at,
                direction=direction
            )

            if direction == 'inbound' and lead.status != 'replied':
                lead.status = 'replied'
                lead.save()

            synced_count += 1
        else:
            print(f"[MS Graph Sync] Ignored Email from: {from_email}, to: {to_email}")

    return synced_count

def _sync_google_gmail(account, user, lead_emails):
    """Sync via Google API."""
    token = account.get_access_token()
    if not token: return 0

    headers = {'Authorization': f'Bearer {token}'}
    # List last 20 messages
    res = requests.get('https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=20', headers=headers)
    
    if res.status_code == 401:
        refresh_token = account.get_refresh_token()
        if refresh_token:
            from django.conf import settings
            client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
            client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }
            token_res = requests.post(token_url, data=data)
            if token_res.ok:
                new_access_token = token_res.json().get('access_token')
                account.set_oauth_tokens(new_access_token, refresh_token)
                account.save()
                headers['Authorization'] = f'Bearer {new_access_token}'
                res = requests.get('https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=20', headers=headers)

    if not res.ok:
        return 0
        
    synced_count = 0
    messages = res.json().get('messages', [])
    
    for m in messages:
        msg_id = m.get('id')
        if EmailMessage.objects.filter(message_id=msg_id).exists():
            continue
            
        # Get full message details
        m_res = requests.get(f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}', headers=headers)
        if m_res.ok:
            msg_data = m_res.json()
            headers_list = msg_data.get('payload', {}).get('headers', [])
            
            subject = next((h['value'] for h in headers_list if h['name'].lower() == 'subject'), '')
            from_email = next((h['value'] for h in headers_list if h['name'].lower() == 'from'), '')
            to_email = next((h['value'] for h in headers_list if h['name'].lower() == 'to'), '')
            
            # Determine direction
            lead = _get_lead_from_email(from_email, user, lead_emails)
            direction = 'inbound'
            
            if not lead:
                lead = _get_lead_from_email(to_email, user, lead_emails)
                direction = 'outbound'

            if lead:
                internal_date = msg_data.get('internalDate')
                # Use datetime.timezone.utc safely
                import datetime as dt
                received_at = dt.datetime.fromtimestamp(int(internal_date)/1000.0, tz=dt.timezone.utc) if internal_date else timezone.now()
                snippet = msg_data.get('snippet', '')
                
                # Try to get plain text body if possible
                body = snippet
                payload = msg_data.get('payload', {})
                parts = payload.get('parts', [])
                import base64
                for part in parts:
                    if part.get('mimeType') == 'text/plain':
                        data = part.get('body', {}).get('data', '')
                        if data:
                            body = base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8')
                            break

                # Clean up quoted replies for a professional look
                import re
                lines = body.splitlines()
                clean_lines = []
                for line in lines:
                    # Break on common reply patterns
                    if re.match(r'^On\s.*wrote:\s*$', line.strip(), re.IGNORECASE) or \
                       re.match(r'^-----Original Message-----', line.strip()) or \
                       re.match(r'^_{10,}$', line.strip()):
                        break
                    if line.startswith('>'):
                        continue
                    clean_lines.append(line)
                
                clean_body = '\n'.join(clean_lines).strip()
                if not clean_body:
                    clean_body = body # fallback if we stripped everything by accident

                print(f"[Sync] Matched Lead {lead.email} - Direction: {direction} - Subject: {subject}")
                EmailMessage.objects.create(
                    user=user,
                    lead=lead,
                    account=account,
                    message_id=msg_id,
                    subject=subject,
                    from_email=from_email,
                    to_email=to_email,
                    body_text=clean_body,
                    received_at=received_at,
                    direction=direction
                )
                
                if direction == 'inbound' and lead.status != 'replied':
                    lead.status = 'replied'
                    lead.save()
                    
                synced_count += 1
            else:
                print(f"[Sync] Ignored Email from: {from_email}, to: {to_email}")
                
    return synced_count
