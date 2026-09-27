"""Server-side OAuth state + PKCE.

The state parameter is the only thing tying an OAuth callback back to the user who
started the flow. It must therefore be unguessable, single-use, expiring, and bound
to the provider it was minted for. Encoding the user id into the value (as the
original implementation did) lets anyone mint a state for any account.
"""
import base64
import secrets
import hashlib
import hmac
from django.db import transaction

from django.utils import timezone

STATE_TTL_SECONDS = 600  # 10 minutes is ample for a consent screen


def _generate_code_verifier():
    return secrets.token_urlsafe(64)[:128]


def code_challenge_for(verifier):
    """S256 challenge derived from the verifier, per RFC 7636."""
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')


def _binding_hash(browser_binding):
    return hashlib.sha256(browser_binding.encode('utf-8')).hexdigest()


def issue_state(user_id, provider, browser_binding):
    """Bind an opaque, expiring state and PKCE verifier to its initiating browser."""
    from .models import OAuthState

    token = secrets.token_urlsafe(32)
    OAuthState.objects.create(
        state=token,
        user_id=user_id,
        provider=provider,
        code_verifier=_generate_code_verifier(),
        browser_binding_hash=_binding_hash(browser_binding),
        expires_at=timezone.now() + timezone.timedelta(seconds=STATE_TTL_SECONDS),
    )
    _purge_expired()
    return token


def consume_state(state, provider, browser_binding):
    """Atomically validate and burn a state. Return (user id, verifier), or None.

    None covers every failure mode on purpose: unknown, forged, wrong provider,
    already used, or expired. Callers must not distinguish between them.
    """
    from .models import OAuthState

    if not state:
        return None

    with transaction.atomic():
        row = OAuthState.objects.select_for_update().filter(
            state=state, provider=provider, used_at__isnull=True,
        ).first()
        if row is None:
            return None

        if row.expires_at < timezone.now():
            row.delete()
            return None

        if not browser_binding or not hmac.compare_digest(
            row.browser_binding_hash, _binding_hash(browser_binding),
        ):
            return None

        now = timezone.now()
        updated = OAuthState.objects.filter(pk=row.pk, used_at__isnull=True).update(used_at=now)
        if not updated:
            return None
        return row.user_id, row.code_verifier


def _purge_expired():
    from .models import OAuthState

    OAuthState.objects.filter(expires_at__lt=timezone.now()).delete()
