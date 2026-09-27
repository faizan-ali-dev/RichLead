"""Server-side OAuth state + PKCE.

The state parameter is the only thing tying an OAuth callback back to the user who
started the flow. It must therefore be unguessable, single-use, expiring, and bound
to the provider it was minted for. Encoding the user id into the value (as the
original implementation did) lets anyone mint a state for any account.
"""
import base64
import hashlib
import secrets

from django.utils import timezone

STATE_TTL_SECONDS = 600  # 10 minutes is ample for a consent screen


def _generate_code_verifier():
    return secrets.token_urlsafe(64)[:128]


def code_challenge_for(verifier):
    """S256 challenge derived from the verifier, per RFC 7636."""
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')


def issue_state(user_id, provider):
    """Mint an opaque single-use state for `user_id` and persist it. Returns the token."""
    from .models import OAuthState

    token = secrets.token_urlsafe(32)
    OAuthState.objects.create(
        state=token,
        user_id=user_id,
        provider=provider,
        code_verifier=_generate_code_verifier(),
        expires_at=timezone.now() + timezone.timedelta(seconds=STATE_TTL_SECONDS),
    )
    _purge_expired()
    return token


def get_code_verifier(state, provider):
    from .models import OAuthState

    row = OAuthState.objects.filter(state=state, provider=provider, used_at__isnull=True).first()
    return row.code_verifier if row else None


def consume_state(state, provider):
    """Validate and burn a state. Returns the originating user id, or None if invalid.

    None covers every failure mode on purpose: unknown, forged, wrong provider,
    already used, or expired. Callers must not distinguish between them.
    """
    from .models import OAuthState

    if not state:
        return None

    row = OAuthState.objects.filter(state=state, provider=provider, used_at__isnull=True).first()
    if row is None:
        return None

    if row.expires_at < timezone.now():
        row.delete()
        return None

    user_id = row.user_id
    row.used_at = timezone.now()
    row.save(update_fields=['used_at'])
    return user_id


def _purge_expired():
    from .models import OAuthState

    OAuthState.objects.filter(expires_at__lt=timezone.now()).delete()
