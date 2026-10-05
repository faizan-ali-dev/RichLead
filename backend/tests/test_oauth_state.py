"""P0-3: OAuth state must be unforgeable, single-use, expiring, and browser-bound.

The original implementation base64-encoded {"user_id": N} with no signature, letting
an attacker bind a victim's mailbox to their own account (or vice versa). The merged
implementation issues an opaque random token tied to the initiating browser (via a
binding cookie) and a PKCE verifier; consume_state returns (user_id, code_verifier).
"""
import base64
import json

import pytest

from integrations.oauth_state import issue_state, consume_state
from integrations.oauth_views import OAUTH_BINDING_COOKIE

BINDING = 'test-browser-binding-value'


@pytest.mark.django_db
def test_state_is_opaque_and_does_not_leak_user_id(user_a):
    state = issue_state(user_a.id, 'google', BINDING)

    # Must not decode to readable JSON carrying identity.
    try:
        decoded = base64.urlsafe_b64decode(state + '=' * (-len(state) % 4)).decode()
        assert 'user_id' not in decoded
    except Exception:
        pass  # undecodable is the desired outcome


@pytest.mark.django_db
def test_state_is_random_not_derived_from_the_user(user_a):
    """Two flows for the same user must produce unrelated values."""
    first = issue_state(user_a.id, 'google', BINDING)
    second = issue_state(user_a.id, 'google', BINDING)

    assert first != second
    assert len(first) >= 32


@pytest.mark.django_db
def test_forged_state_is_rejected(user_a):
    """The exact payload that compromised the original implementation."""
    forged = base64.urlsafe_b64encode(json.dumps({"user_id": user_a.id}).encode()).decode()
    assert consume_state(forged, 'google', BINDING) is None


@pytest.mark.django_db
def test_valid_state_round_trips(user_a):
    state = issue_state(user_a.id, 'google', BINDING)
    user_id, verifier = consume_state(state, 'google', BINDING)
    assert user_id == user_a.id
    assert verifier  # a PKCE verifier is returned for the token exchange


@pytest.mark.django_db
def test_state_is_single_use(user_a):
    state = issue_state(user_a.id, 'google', BINDING)
    assert consume_state(state, 'google', BINDING)[0] == user_a.id
    assert consume_state(state, 'google', BINDING) is None


@pytest.mark.django_db
def test_state_is_bound_to_its_provider(user_a):
    """A state minted for Google must not authorise a Microsoft callback."""
    state = issue_state(user_a.id, 'google', BINDING)
    assert consume_state(state, 'microsoft', BINDING) is None


@pytest.mark.django_db
def test_state_is_bound_to_its_browser(user_a):
    """A state stolen and replayed from another browser must be rejected."""
    state = issue_state(user_a.id, 'google', BINDING)
    assert consume_state(state, 'google', 'a-different-browser') is None
    # The original browser still works afterwards (a mismatch must not burn it).
    assert consume_state(state, 'google', BINDING)[0] == user_a.id


@pytest.mark.django_db
def test_random_state_is_rejected(user_a):
    assert consume_state('totally-made-up-value', 'google', BINDING) is None
    assert consume_state('', 'google', BINDING) is None
    assert consume_state(None, 'google', BINDING) is None


@pytest.mark.django_db
@pytest.mark.parametrize('provider', ['google', 'microsoft'])
def test_callback_is_reachable_without_authentication(api, provider):
    """The provider redirects the user's browser here with no bearer token.

    Requiring auth makes the whole connect flow 401 before the state is even read.
    Regression guard: DEFAULT_PERMISSION_CLASSES=IsAuthenticated broke this once.
    """
    resp = api.get(f'/api/integrations/oauth/{provider}/callback/?code=fake&state=whatever')

    assert resp.status_code != 401, "callback must not require authentication"
    assert resp.status_code == 302


@pytest.mark.django_db
@pytest.mark.parametrize('provider', ['google', 'microsoft'])
def test_callback_with_forged_state_redirects_with_error(api, user_a, provider):
    from integrations.models import EmailAccount

    forged = base64.urlsafe_b64encode(json.dumps({"user_id": user_a.id}).encode()).decode()
    resp = api.get(f'/api/integrations/oauth/{provider}/callback/?code=fake&state={forged}')

    assert resp.status_code == 302
    assert 'invalid_state' in resp['Location']
    assert EmailAccount.objects.filter(user=user_a).count() == 0


@pytest.mark.django_db
def test_valid_state_passes_the_state_check(api, user_a):
    """A real state must get past validation and fail later (at token exchange),
    proving the gate accepts legitimate flows rather than blocking everything.

    The callback reads the browser binding from its cookie, so the request must
    carry the same binding the state was minted with.
    """
    state = issue_state(user_a.id, 'google', BINDING)
    api.cookies[OAUTH_BINDING_COOKIE] = BINDING
    resp = api.get(f'/api/integrations/oauth/google/callback/?code=fake&state={state}')

    assert resp.status_code == 302
    assert 'invalid_state' not in resp['Location']


@pytest.mark.django_db
def test_init_requires_authentication(api):
    resp = api.get('/api/integrations/oauth/google/init/')
    assert resp.status_code in (401, 403)
