import os
import imaplib
import email
import re
import logging
from datetime import datetime, timedelta
from email.header import decode_header
from html import unescape

import requests
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import EmailMessage
from integrations.network import PublicIMAP4SSL, validate_public_mail_server
from leads.models import Lead
from integrations.models import EmailAccount

logger = logging.getLogger(__name__)

def sync_emails_for_user(user):
    """
    Syncs emails for all connected accounts of a user.
    Only saves emails that match a Lead's email address.
    """
    accounts = EmailAccount.objects.filter(user=user, is_connected=True)
    # Cache all lead emails for quick lookup
    lead_emails = {e.lower() for e in Lead.objects.filter(user=user).values_list('email', flat=True) if e}
    
    if not lead_emails:
        return {"success": True, "message": "No leads to sync against."}

    total_synced = 0
    sync_errors = []
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
        except Exception:
            logger.exception('Mailbox sync failed for account %s', account.pk)
            sync_errors.append({'account_id': account.pk, 'error': 'Mailbox sync failed.'})

    return {
        'success': not sync_errors,
        'synced_count': total_synced,
        'sync_errors': sync_errors,
    }

# A message we sent reappears in the mailbox moments later, in Sent/All Mail.
# Restrict body-based matching to a short window so a later intentional resend
# with the same subject and content remains a separate message.
OUTBOUND_ECHO_WINDOW = timedelta(minutes=5)


def _normalized_body(body):
    return re.sub(r'\s+', ' ', unescape(body or '')).strip().casefold()


def _normalized_body_length(body):
    return len(_normalized_body(body))


def same_outbound_body(first, second):
    """Match an outbound message and a provider's truncated copy of that message."""
    first = _normalized_body(first)
    second = _normalized_body(second)
    if not first or not second:
        return False
    if first == second:
        return True

    shorter, longer = sorted((first, second), key=len)
    # Providers sometimes return only the first part of the sent body. Require a
    # substantial prefix so ordinary short messages are never merged by accident.
    return len(shorter) >= 100 and longer.startswith(shorter)


def _is_send_time_message_id(message_id):
    return (message_id or '').startswith('sent-')


def _find_existing_message(user, *, message_id, rfc_message_id, lead,
                           direction, subject, received_at, body_text):
    if message_id:
        existing = EmailMessage.objects.filter(user=user, message_id=message_id).first()
        if existing:
            return existing

    if rfc_message_id:
        existing = EmailMessage.objects.filter(
            user=user, rfc_message_id=rfc_message_id,
        ).first()
        if existing:
            return existing

    if direction == 'outbound' and lead is not None and body_text:
        when = received_at or timezone.now()
        candidates = EmailMessage.objects.filter(
            user=user,
            lead=lead,
            direction='outbound',
            subject__iexact=(subject or '')[:500],
            received_at__gte=when - OUTBOUND_ECHO_WINDOW,
            received_at__lte=when + OUTBOUND_ECHO_WINDOW,
        ).order_by('-received_at')
        for candidate in candidates:
            # Body matching is only a fallback for a send-time row versus a
            # provider's Sent-folder copy. Never collapse two actual send rows
            # merely because a user sent the same body twice in quick succession.
            if (
                _is_send_time_message_id(candidate.message_id)
                != _is_send_time_message_id(message_id)
                and same_outbound_body(candidate.body_text, body_text)
            ):
                return candidate

    return None


def is_already_recorded(user, *, message_id, rfc_message_id='', lead=None,
                        direction='inbound', subject='', received_at=None,
                        body_text=''):
    """True when this message is already stored, including as our own send.

    Outbound mail is written once at send time and then shows up again during the
    next mailbox sync under the provider's own id. Matching only on the provider
    id therefore stores the same email twice, which is what produced duplicate
    thread entries. Matched in order of reliability:

      1. provider id  -- exact, covers ordinary re-syncs
      2. RFC Message-ID -- stable across mailboxes, set by us on SMTP and Gmail sends
      3. body + lead + subject + short time window -- fallback for a provider
         echo where Graph's sendMail did not give us an id
    """
    return _find_existing_message(
        user,
        message_id=message_id,
        rfc_message_id=rfc_message_id,
        lead=lead,
        direction=direction,
        subject=subject,
        received_at=received_at,
        body_text=body_text,
    ) is not None


def record_email_message(*, user, lead, account, message_id, rfc_message_id='',
                         subject='', from_email='', to_email='', body_text='',
                         body_html='', received_at=None, direction='inbound'):
    """Save one message while serializing sends and mailbox echoes per lead.

    Auto-sync can read a just-sent mail before the send request records its own
    copy. Locking the lead around match-and-save closes that race on PostgreSQL.
    """
    when = received_at or timezone.now()
    try:
        with transaction.atomic():
            if lead is not None:
                Lead.objects.select_for_update().only('id').get(pk=lead.pk, user=user)

            existing = _find_existing_message(
                user,
                message_id=message_id,
                rfc_message_id=rfc_message_id,
                lead=lead,
                direction=direction,
                subject=subject,
                received_at=when,
                body_text=body_text,
            )
            if existing:
                changed_fields = []
                incoming_body = body_text or ''
                if _normalized_body_length(incoming_body) > _normalized_body_length(existing.body_text):
                    existing.body_text = incoming_body
                    changed_fields.append('body_text')
                    if body_html:
                        existing.body_html = body_html
                        changed_fields.append('body_html')
                if rfc_message_id and not existing.rfc_message_id:
                    existing.rfc_message_id = rfc_message_id
                    changed_fields.append('rfc_message_id')
                if account is not None and existing.account_id is None:
                    existing.account = account
                    changed_fields.append('account')
                if changed_fields:
                    existing.save(update_fields=changed_fields)
                return False

            EmailMessage.objects.create(
                user=user,
                lead=lead,
                account=account,
                message_id=message_id,
                rfc_message_id=rfc_message_id,
                subject=subject,
                from_email=from_email,
                to_email=to_email,
                body_text=body_text,
                body_html=body_html,
                received_at=when,
                direction=direction,
            )
            return True
    except IntegrityError:
        # The database's provider-id uniqueness constraint is the final guard if
        # an external provider returns the same id concurrently on two accounts.
        if message_id and EmailMessage.objects.filter(user=user, message_id=message_id).exists():
            return False
        raise


def deduplicate_outbound_echoes(messages):
    """Hide legacy send/sync echoes in inbox results without deleting stored rows."""
    visible = []
    buckets = {}
    for message in messages:
        if message.direction != 'outbound' or message.lead_id is None:
            visible.append(message)
            continue

        minute = message.received_at.replace(second=0, microsecond=0)
        bucket_key = (
            message.lead_id,
            (message.subject or '').strip().casefold(),
            minute,
        )
        duplicate_index = next((
            index for index in buckets.get(bucket_key, [])
            if (
                (
                    visible[index].rfc_message_id
                    and visible[index].rfc_message_id == message.rfc_message_id
                )
                or (
                    _is_send_time_message_id(visible[index].message_id)
                    != _is_send_time_message_id(message.message_id)
                )
            ) and same_outbound_body(visible[index].body_text, message.body_text)
        ), None)
        if duplicate_index is None:
            buckets.setdefault(bucket_key, []).append(len(visible))
            visible.append(message)
            continue

        # Keep the complete send-time copy when its mailbox echo is truncated.
        if _normalized_body_length(message.body_text) > _normalized_body_length(
            visible[duplicate_index].body_text
        ):
            visible[duplicate_index] = message

    return sorted(visible, key=lambda message: message.received_at, reverse=True)


def html_to_text(html):
    """Readable plain text from an HTML body.

    Graph returns HTML for most messages; storing it raw leaves entities like
    &#39; visible in the UI.
    """
    if not html:
        return ''

    text = re.sub(r'(?is)<(script|style).*?</\1>', ' ', html)
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)</(?:p|div|li|tr|h[1-6])\s*>', '\n', text)
    text = re.sub(r'(?i)<blockquote\b[^>]*>', '\n', text)
    text = re.sub(r'(?i)</blockquote\s*>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def mark_replied(lead, when=None):
    """Record an inbound reply. Idempotent, and never downgrades a blacklist."""
    fields = []
    if lead.replied_at is None:
        lead.replied_at = when or timezone.now()
        fields.append('replied_at')

    # 'blacklisted' is an opt-out and outranks everything.
    if lead.status not in ('replied', 'blacklisted'):
        lead.status = 'replied'
        fields.append('status')

    if fields:
        lead.save(update_fields=fields)


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
        validate_public_mail_server(account.imap_host, account.imap_port)
        mail = PublicIMAP4SSL(account.imap_host, account.imap_port, timeout=10)
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
                    rfc_message_id = (msg.get("Message-ID", "") or "").strip()
                    message_id = rfc_message_id or f"imap-{num.decode()}"
                    
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
                        # Extract the body before dedupe so a truncated provider
                        # echo can be matched and upgraded to the full send copy.
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode()
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode()

                        created = record_email_message(
                            user=user,
                            lead=lead,
                            account=account,
                            message_id=message_id,
                            rfc_message_id=rfc_message_id,
                            subject=subject,
                            from_email=from_email,
                            to_email=to_email,
                            body_text=body,
                            received_at=received_at,
                            direction=direction,
                        )
                        if created:
                            # The Graph and Gmail paths did this but IMAP never did,
                            # leaving every SMTP tenant on a permanent 0% reply rate.
                            if direction == 'inbound':
                                mark_replied(lead, received_at)
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
    res = requests.get('https://graph.microsoft.com/v1.0/me/messages?$top=30&$select=id,internetMessageId,subject,from,toRecipients,receivedDateTime,body,isRead', headers=headers)
    
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
                res = requests.get('https://graph.microsoft.com/v1.0/me/messages?$top=30&$select=id,internetMessageId,subject,from,toRecipients,receivedDateTime,body,isRead', headers=headers)

    if not res.ok:
        print(f"[MS Graph Sync Error] Status: {res.status_code}, Body: {res.text}")
        return 0

    synced_count = 0
    messages_list = res.json().get('value', [])

    # Also check Junk Email folder in case incoming lead reply was categorized as Junk by MS filters
    try:
        junk_res = requests.get('https://graph.microsoft.com/v1.0/me/mailFolders/junkemail/messages?$top=15&$select=id,internetMessageId,subject,from,toRecipients,receivedDateTime,body,isRead', headers=headers)
        if junk_res.ok:
            existing_ids = {m.get('id') for m in messages_list if m.get('id')}
            for jm in junk_res.json().get('value', []):
                if jm.get('id') not in existing_ids:
                    messages_list.append(jm)
    except Exception as je:
        print(f"[MS Graph Junk Folder Check Error]: {je}")

    for msg in messages_list:
        message_id = msg.get('id')
        if not message_id:
            continue

        subject = msg.get('subject', '')
        rfc_message_id = msg.get('internetMessageId', '') or ''
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

            # Use the full body, never bodyPreview -- the preview is truncated and
            # HTML-escaped, which is what put "I&#39;m ..." into the thread view.
            body_info = msg.get('body', {}) or {}
            body_content = body_info.get('content', '')
            body_text = (
                html_to_text(body_content)
                if (body_info.get('contentType', '') or '').lower() == 'html'
                else body_content
            )

            print(f"[MS Graph Sync] Matched Lead {lead.email} - Direction: {direction} - Subject: {subject}")
            created = record_email_message(
                user=user,
                lead=lead,
                account=account,
                message_id=message_id,
                rfc_message_id=rfc_message_id,
                subject=subject,
                from_email=from_email,
                to_email=to_email,
                body_text=body_text,
                body_html=body_content,
                received_at=received_at,
                direction=direction,
            )

            if created:
                if direction == 'inbound':
                    mark_replied(lead, received_at)
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
        if not msg_id:
            continue
            
        # Get full message details
        m_res = requests.get(f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}', headers=headers)
        if m_res.ok:
            msg_data = m_res.json()
            headers_list = msg_data.get('payload', {}).get('headers', [])
            
            subject = next((h['value'] for h in headers_list if h['name'].lower() == 'subject'), '')
            from_email = next((h['value'] for h in headers_list if h['name'].lower() == 'from'), '')
            to_email = next((h['value'] for h in headers_list if h['name'].lower() == 'to'), '')
            rfc_message_id = next((h['value'] for h in headers_list if h['name'].lower() == 'message-id'), '')
            
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
                created = record_email_message(
                    user=user,
                    lead=lead,
                    account=account,
                    message_id=msg_id,
                    rfc_message_id=rfc_message_id,
                    subject=subject,
                    from_email=from_email,
                    to_email=to_email,
                    body_text=clean_body,
                    received_at=received_at,
                    direction=direction,
                )
                
                if created:
                    if direction == 'inbound':
                        mark_replied(lead, received_at)
                    
                    synced_count += 1
            else:
                print(f"[Sync] Ignored Email from: {from_email}, to: {to_email}")
                
    return synced_count
