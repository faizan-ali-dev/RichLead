"""Signed one-click unsubscribe tokens.

CAN-SPAM s.5 requires a working opt-out in every commercial email, and RFC 8058
one-click unsubscribe is now effectively mandatory for bulk senders at Gmail and
Yahoo. Tokens are signed rather than stored so they never expire and cost no lookup.
"""
from django.core import signing

SALT = 'richlead.unsubscribe'


def make_token(user_id, lead_id):
    return signing.dumps({'u': user_id, 'l': lead_id}, salt=SALT)


def resolve_token(token):
    """Return (user_id, lead_id), or None if the token is absent or tampered with."""
    if not token:
        return None
    try:
        data = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None
    return data.get('u'), data.get('l')


def unsubscribe_url(user_id, lead_id, base_url):
    return f"{base_url.rstrip('/')}/api/integrations/unsubscribe/{make_token(user_id, lead_id)}/"
