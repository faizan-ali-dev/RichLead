import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from leads.models import Lead
from .models import EmailAccount

def send_outreach_email(lead_id, user, message_body, account_id=None, subject=None):
    """
    Sends an email to the lead using the user's connected SMTP/OAuth account.
    If account_id is provided, it uses that specific account. Otherwise it uses the first connected one.
    """
    try:
        lead = Lead.objects.get(id=lead_id, user=user)
    except Lead.DoesNotExist:
        return {"success": False, "error": "Lead not found."}

    # Fetch user's email account
    if account_id and str(account_id) != 'rotate':
        email_account = EmailAccount.objects.filter(id=account_id, user=user, is_connected=True).first()
    else:
        connected_accounts = list(EmailAccount.objects.filter(user=user, is_connected=True).order_by('id'))
        if connected_accounts:
            email_account = connected_accounts[lead.id % len(connected_accounts)]
        else:
            email_account = None
        
    # Dynamic Subject Line Logic
    if subject:
        final_subject = subject
    else:
        import random
        if lead.status == 'pending':
            # First touch subjects (Rotated to avoid spam)
            subjects = [
                f"Question about {lead.company}",
                f"Thoughts on {lead.company}?",
                f"Idea for {lead.company}",
                f"Connecting with {lead.name}"
            ]
            # Use lead.id to pick deterministically so it doesn't change on refresh, but varies across leads
            final_subject = subjects[lead.id % len(subjects)]
        else:
            # Follow up subjects
            subjects = [
                f"Following up on {lead.company}",
                f"Any updates on {lead.company}?",
                f"Re: {lead.company}"
            ]
            final_subject = subjects[lead.id % len(subjects)]
    
    if not email_account:
        # Sandbox/Mock Mode if no account is configured
        print(f"\n--- MOCK EMAIL SEND ---")
        print(f"To: {lead.email}")
        print(f"Subject: {final_subject}")
        print(f"Body:\n{message_body}")
        print(f"-----------------------\n")
        
        # Update lead status
        lead.status = 'reached'
        lead.save()
        
        # Save to Inbox
        from inbox.models import EmailMessage
        from django.utils import timezone
        import uuid
        
        EmailMessage.objects.create(
            user=user,
            lead=lead,
            account=None,
            message_id=f"sent-mock-{uuid.uuid4()}",
            subject=final_subject,
            from_email="sandbox@richlead.ai",
            to_email=lead.email,
            body_text=message_body,
            received_at=timezone.now(),
            direction='outbound'
        )
        
        return {"success": True, "message": "Email sent (Sandbox Mode)"}

    # Real Sending via SMTP or API
    try:
        sender_email = email_account.email_address
        receiver_email = lead.email

        if email_account.auth_type == 'smtp':
            if not email_account.smtp_host:
                return {"success": False, "error": "SMTP Host is missing."}
            password = email_account.get_password()
            msg = MIMEMultipart()
            import email.utils
            
            # Use a real-sounding name instead of 'admin' to avoid spam filters
            display_name = user.get_full_name().strip()
            if not display_name or display_name.lower() == 'admin':
                prefix = sender_email.split('@')[0]
                display_name = prefix.replace('.', ' ').replace('_', ' ').title()
                
            msg['From'] = email.utils.formataddr((display_name, sender_email))
            msg['To'] = receiver_email
            msg['Subject'] = final_subject
            msg['Date'] = email.utils.formatdate(localtime=True)
            msg['Message-ID'] = email.utils.make_msgid(domain=sender_email.split('@')[-1])
            msg.attach(MIMEText(message_body, 'plain', 'utf-8'))

            if email_account.smtp_port == 465:
                server = smtplib.SMTP_SSL(email_account.smtp_host, email_account.smtp_port)
            else:
                server = smtplib.SMTP(email_account.smtp_host, email_account.smtp_port)
                server.starttls()
                
            server.login(sender_email, password)
            server.send_message(msg)
            server.quit()

        elif email_account.auth_type == 'oauth_google':
            import base64
            import requests
            from django.conf import settings
            token = email_account.get_access_token()
            import email.utils
            
            # Use a real-sounding name instead of 'admin' to avoid spam filters
            display_name = user.get_full_name().strip()
            if not display_name or display_name.lower() == 'admin':
                # Try to derive name from email (e.g. faizan.ali@ -> Faizan Ali)
                prefix = email_account.email_address.split('@')[0]
                display_name = prefix.replace('.', ' ').replace('_', ' ').title()
                
            msg = MIMEText(message_body, 'plain', 'utf-8')
            msg['To'] = receiver_email
            msg['From'] = email.utils.formataddr((display_name, email_account.email_address))
            msg['Subject'] = final_subject
            msg['Date'] = email.utils.formatdate(localtime=True)
            msg['Message-ID'] = email.utils.make_msgid(domain=email_account.email_address.split('@')[-1])
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
            from django.conf import settings
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
                    "body": {"contentType": "Text", "content": message_body},
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
        lead.status = 'reached'
        lead.save()
        
        # Save to Inbox
        from inbox.models import EmailMessage
        from django.utils import timezone
        import uuid
        
        EmailMessage.objects.create(
            user=user,
            lead=lead,
            account=email_account,
            message_id=f"sent-{uuid.uuid4()}",
            subject=final_subject,
            from_email=sender_email,
            to_email=receiver_email,
            body_text=message_body,
            received_at=timezone.now(),
            direction='outbound'
        )

        return {"success": True, "message": f"Email sent successfully via {sender_email}"}

    except Exception as e:
        return {"success": False, "error": f"Send Error: {str(e)}"}
