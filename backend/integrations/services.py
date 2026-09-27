import logging
import smtplib
import ssl
from .network import connect_smtp, validate_public_mail_server
from email.mime.text import MIMEText

from django.conf import settings
from django.utils import timezone

from leads.models import Lead
from .models import EmailAccount, is_suppressed
from .unsubscribe import make_token

logger = logging.getLogger(__name__)

# Statuses that must never be overwritten by a send. 'blacklisted' is an opt-out and
# 'replied' is a real outcome; regressing either to 'reached' destroys the record.
TERMINAL_STATUSES = {'blacklisted', 'replied'}


def _mark_reached(lead):
    """Record the send, without ever clobbering a terminal status.

    first_sent_at is set once and never overwritten, so follow-ups don't reset the
    campaign clock and the sent-count stays stable.
    """

    fields = []
    if lead.first_sent_at is None:
        lead.first_sent_at = timezone.now()
        fields.append('first_sent_at')

    if lead.status not in TERMINAL_STATUSES:
        lead.status = 'reached'
        fields.append('status')

    if fields:
        lead.save(update_fields=fields)


def resolve_subject(lead, explicit_subject=None):
    """The subject to send with, in priority order.

    Prefers the subject the model wrote alongside the body, because a subject
    that matches its body is itself a deliverability factor. Falls back to a
    plain, non-deceptive line.

    Deliberately never fabricates "Re:" or "Fwd:". Faking a reply to a
    conversation that never happened is a CAN-SPAM s.5(a)(2) violation and one
    of the strongest spam signals there is.
    """
    if explicit_subject and explicit_subject.strip():
        return explicit_subject.strip()[:255]

    research = getattr(lead, 'research', None)
    if research and research.generated_subject.strip():
        return research.generated_subject.strip()[:255]

    return f"question about {lead.company}"[:255]


def unsubscribe_url(user, lead):
    base = getattr(settings, 'BACKEND_URL', 'http://localhost:8000').rstrip('/')
    return f"{base}/api/integrations/unsubscribe/{make_token(user.id, lead.id)}/"


def _unsubscribe_headers(user, lead):
    """RFC 8058 one-click unsubscribe headers, when the tenant opts into them.

    These satisfy the Gmail/Yahoo bulk-sender requirement, but they are also a
    bulk-mail marker and one of the strongest Promotions-tab signals there is.
    Tenants sending 1:1 volumes are better served by a plain-text opt-out, which
    is equally compliant under CAN-SPAM. See User.unsubscribe_mode.
    """
    if getattr(user, 'unsubscribe_mode', 'text') not in ('header', 'both'):
        return {}

    url = unsubscribe_url(user, lead)
    return {
        'List-Unsubscribe': f'<{url}>',
        'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
    }


def apply_unsubscribe_text(user, body):
    """Append the plain-text opt-out line when that mode is selected.

    A sentence a human would write beats a footer. "Click here to unsubscribe"
    is itself a Promotions-tab trigger, so the default wording asks for a reply.
    """
    if getattr(user, 'unsubscribe_mode', 'text') not in ('text', 'both'):
        return body

    line = (getattr(user, 'unsubscribe_text', '') or '').strip()
    if not line or line.lower() in body.lower():
        return body

    return f"{body.rstrip()}\n\n{line}"


def pick_sending_account(user):
    """Least-loaded connected mailbox with quota left.

    Keying rotation on lead.id (the previous approach) ignored actual volume and
    reshuffled every assignment whenever an account was removed.
    """
    candidates = [
        a for a in EmailAccount.objects.filter(user=user, is_connected=True)
        if a.remaining_sends_today() > 0
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda a: (a.sends_today if a.sends_counted_on == timezone.now().date() else 0, a.id))


def send_outreach_email(lead_id, user, message_body, account_id=None, subject=None):
    """
    Sends an email to the lead using the user's connected SMTP/OAuth account.
    If account_id is provided, it uses that specific account. Otherwise it uses the first connected one.
    """
    try:
        lead = Lead.objects.get(id=lead_id, user=user)
    except Lead.DoesNotExist:
        return {"success": False, "error": "Lead not found."}

    # Compliance gate. Must run before anything else touches the lead or the network.
    if lead.status == 'blacklisted':
        return {"success": False, "error": "Lead is blacklisted and cannot be contacted."}

    if is_suppressed(user, lead.email):
        return {"success": False, "error": "Recipient is on your suppression list."}

    # Fetch user's email account
    if account_id and str(account_id) != 'rotate':
        email_account = EmailAccount.objects.filter(id=account_id, user=user, is_connected=True).first()
    else:
        email_account = pick_sending_account(user)

    if email_account and email_account.remaining_sends_today() <= 0:
        return {
            "success": False,
            "error": f"Daily send limit reached for {email_account.email_address}. "
                     f"Sending more risks suspension by the provider.",
        }

    final_subject = resolve_subject(lead, subject)

    if not email_account:
        # Reporting success for mail that was never sent is the worst possible default:
        # users mid-onboarding believe campaigns are live, and the leads get burned to
        # 'reached' so they are never retried. Sandbox must be opted into explicitly.
        if not getattr(settings, 'ALLOW_SANDBOX_SEND', False):
            return {
                "success": False,
                "error": "No connected sender account. Connect a mailbox under Sender Accounts before sending.",
            }

        logger.info("SANDBOX send to %s subject=%r (not delivered)", lead.email, final_subject)

        # Deliberately NOT written to the mailbox. The inbox is a record of mail
        # that actually reached someone; a sandbox message reached nobody.
        _mark_reached(lead)

        return {"success": True, "sandbox": True, "message": "Sandbox mode: message was NOT delivered."}

    # Real Sending via SMTP or API
    try:
        sender_email = email_account.email_address
        receiver_email = lead.email

        # Recorded below so the mailbox sync can recognise this message as one we
        # sent, rather than storing a second copy of it when it reappears in the
        # Sent folder. Graph's sendMail does not let us set it, so it stays blank
        # there and the sync falls back to a subject/timestamp match.
        rfc_message_id = ''

        # Exactly what goes on the wire, opt-out line included, so the stored
        # copy matches what the recipient actually received.
        sent_body = apply_unsubscribe_text(user, message_body)

        if email_account.auth_type == 'smtp':
            if not email_account.smtp_host:
                return {"success": False, "error": "SMTP Host is missing."}
            validate_public_mail_server(email_account.smtp_host, email_account.smtp_port)
            password = email_account.get_password()
            import email.utils

            # A bare text/plain part, NOT multipart. A person writing from Gmail
            # or Outlook sends text/plain; a single-part multipart/mixed wrapper
            # is a "this was machine-generated" signal and pushes Gmail to
            # classify the message as Promotions.
            msg = MIMEText(sent_body, 'plain', 'utf-8')

            # Use a real-sounding name instead of 'admin' to avoid spam filters
            display_name = user.get_full_name().strip()
            if not display_name or display_name.lower() == 'admin':
                prefix = sender_email.split('@')[0]
                display_name = prefix.replace('.', ' ').replace('_', ' ').title()

            msg['From'] = email.utils.formataddr((display_name, sender_email))
            msg['To'] = receiver_email
            msg['Subject'] = final_subject
            msg['Date'] = email.utils.formatdate(localtime=True)
            rfc_message_id = email.utils.make_msgid(domain=sender_email.split('@')[-1])
            msg['Message-ID'] = rfc_message_id
            for header, value in _unsubscribe_headers(user, lead).items():
                msg[header] = value

            if email_account.smtp_port == 465:
                server = connect_smtp(email_account.smtp_host, email_account.smtp_port, implicit_tls=True)
            else:
                server = connect_smtp(email_account.smtp_host, email_account.smtp_port)
                server.starttls(context=ssl.create_default_context())
                
            server.login(sender_email, password)
            server.send_message(msg)
            server.quit()

        elif email_account.auth_type == 'oauth_google':
            import base64
            import requests
            token = email_account.get_access_token()
            import email.utils
            
            # Use a real-sounding name instead of 'admin' to avoid spam filters
            display_name = user.get_full_name().strip()
            if not display_name or display_name.lower() == 'admin':
                # Try to derive name from email (e.g. faizan.ali@ -> Faizan Ali)
                prefix = email_account.email_address.split('@')[0]
                display_name = prefix.replace('.', ' ').replace('_', ' ').title()
                
            msg = MIMEText(sent_body, 'plain', 'utf-8')
            msg['To'] = receiver_email
            msg['From'] = email.utils.formataddr((display_name, email_account.email_address))
            msg['Subject'] = final_subject
            msg['Date'] = email.utils.formatdate(localtime=True)
            rfc_message_id = email.utils.make_msgid(domain=email_account.email_address.split('@')[-1])
            msg['Message-ID'] = rfc_message_id
            for header, value in _unsubscribe_headers(user, lead).items():
                msg[header] = value
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
            res = requests.post('https://gmail.googleapis.com/gmail/v1/users/me/messages/send', headers=headers, json={'raw': raw})
            
            # If token expired, try to refresh
            if res.status_code == 401:
                refresh_token = email_account.get_refresh_token()
                if refresh_token:
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
                        email_account.set_oauth_tokens(new_access_token, refresh_token)
                        email_account.save()
                        # Retry with new token
                        headers['Authorization'] = f'Bearer {new_access_token}'
                        res = requests.post('https://gmail.googleapis.com/gmail/v1/users/me/messages/send', headers=headers, json={'raw': raw})
            
            if not res.ok:
                return {"success": False, "error": f"Google API Error: {res.text}"}

        elif email_account.auth_type == 'oauth_microsoft':
            import requests
            token = email_account.get_access_token()
            headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
            
            # Proper display name to build sender trust and avoid spam flags
            display_name = user.get_full_name().strip()
            if not display_name or display_name.lower() == 'admin':
                prefix = email_account.email_address.split('@')[0]
                display_name = prefix.replace('.', ' ').replace('_', ' ').title()

            data = {
                "message": {
                    "subject": final_subject,
                    "body": {"contentType": "Text", "content": sent_body},
                    "toRecipients": [{"emailAddress": {"address": receiver_email}}],
                    "from": {
                        "emailAddress": {
                            "name": display_name,
                            "address": email_account.email_address
                        }
                    },
                    "replyTo": [
                        {
                            "emailAddress": {
                                "name": display_name,
                                "address": email_account.email_address
                            }
                        }
                    ]
                },
                "saveToSentItems": True
            }
            res = requests.post('https://graph.microsoft.com/v1.0/me/sendMail', headers=headers, json=data)
            
            if res.status_code == 401:
                refresh_token = email_account.get_refresh_token()
                if refresh_token:
                    client_id = getattr(settings, 'MICROSOFT_CLIENT_ID', '')
                    client_secret = getattr(settings, 'MICROSOFT_CLIENT_SECRET', '')
                    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
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
                        email_account.set_oauth_tokens(new_access_token, new_refresh_token)
                        email_account.save()
                        headers['Authorization'] = f'Bearer {new_access_token}'
                        res = requests.post('https://graph.microsoft.com/v1.0/me/sendMail', headers=headers, json=data)

            if not res.ok:
                err_text = res.text
                if 'ErrorNonExistentMailbox' in err_text:
                    return {
                        "success": False, 
                        "error": f"Microsoft Mailbox Error: Please visit https://account.live.com/names/Manage and click 'Make primary' next to {email_account.email_address}. Microsoft requires your @outlook.com address to be the Primary Alias to activate its sending mailbox."
                    }
                return {"success": False, "error": f"Microsoft Graph API Error: {err_text}"}

        # Update lead status
        _mark_reached(lead)
        
        # Save to Inbox
        from inbox.models import EmailMessage
        import uuid
        
        EmailMessage.objects.create(
            user=user,
            lead=lead,
            account=email_account,
            message_id=rfc_message_id or f"sent-{uuid.uuid4()}",
            rfc_message_id=rfc_message_id,
            subject=final_subject,
            from_email=sender_email,
            to_email=receiver_email,
            body_text=sent_body,
            received_at=timezone.now(),
            direction='outbound'
        )

        email_account.record_send()

        return {"success": True, "message": f"Email sent successfully via {sender_email}"}

    except Exception as e:
        return {"success": False, "error": f"Send Error: {str(e)}"}
