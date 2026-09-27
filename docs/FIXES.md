# RichLead — Remediation Log

**Date:** 2026-09-26
**Companion to:** [CODE_REVIEW.md](CODE_REVIEW.md)
**Result:** 81 backend tests passing · `manage.py check --deploy` clean · all 11 frontend routes 200

Every fix below was driven by a test written **before** the change, confirmed failing against the
original code, then confirmed passing. Each was also exercised against a live running instance.

---

## Test infrastructure (new)

There was no test suite — all four `tests.py` files were untouched Django stubs, which is why
bugs like the Prospecting crash survived. Added `pytest` + `pytest-django`:

| File | Covers |
|---|---|
| `tests/conftest.py` | Two-tenant fixtures (`user_a`/`user_b`) for isolation testing |
| `tests/test_tenant_isolation.py` | Per-user uniqueness, cross-tenant reads |
| `tests/test_suppression.py` | Blacklist enforcement, status regression, suppression API |
| `tests/test_oauth_state.py` | State forgery, replay, provider binding |
| `tests/test_crypto.py` | Key sourcing, round-trip, loud failure |
| `tests/test_prospecting.py` | Lead creation, caps, autopilot vs suppression |
| `tests/test_settings_hardening.py` | Permissions, pagination, throttling, CORS |
| `tests/test_dashboard_stats.py` | Reply-rate arithmetic, query budget |
| `tests/test_auth.py` | Token lifetime, rotation, replay, email uniqueness |
| `tests/test_sending_safety.py` | Send caps, rotation, unsubscribe, N+1 budgets |

```bash
cd backend && source venv/bin/activate && DEBUG=True python -m pytest
```

---

## P0 — Blockers (all closed)

### 1. Tenant isolation · `leads/models.py`, `inbox/models.py`, `inbox/services.py`

`Lead.email` and `EmailMessage.message_id` were **globally** unique. Replaced with
`UniqueConstraint(user, email)` / `(user, message_id)`, added covering indexes, and added the
missing `user=` filter to all three inbox dedupe queries. Emails are now normalised to lowercase
on save. Migration `leads/0004` dedupes and lowercases existing rows before the constraint applies.

> Before: User B could not add a prospect User A already had.
> After: both tenants keep their own row; duplicates within one tenant still rejected.

### 2. Suppression enforcement · `integrations/services.py`, `integrations/models.py`

Added `SuppressionEntry` (per-tenant, address or whole domain) and a compliance gate at the top of
`send_outreach_email()` that runs **before** any network call. `_mark_reached()` now refuses to
overwrite `blacklisted` or `replied`.

> Before: a blacklisted lead was emailed *and* its status silently rewritten to `reached`,
> destroying the opt-out record so it would repeat forever.
> After: send refused, blacklist preserved.

### 3. OAuth state · `integrations/oauth_state.py` (new), `integrations/oauth_views.py`

Replaced base64 `{"user_id": N}` with an opaque `secrets.token_urlsafe(32)` persisted in a new
`OAuthState` model — single-use, 10-minute TTL, bound to its provider. Added **PKCE (S256)** to
both flows. Redirect URIs are now env-driven rather than hardcoded to localhost.

> Before: `eyJ1c2VyX2lkIjogMX0=` bound any mailbox to any account — full mailbox compromise.
> After (live): `302 → ?error=invalid_state`.

### 4. Credential encryption · `integrations/models.py`, `richlead_backend/settings.py`

Removed the hardcoded Fernet key. `FERNET_KEY` and `SECRET_KEY` now come from the environment and
**startup fails without them** when `DEBUG=False`. In DEBUG a generated key is cached under
`backend/.dev-secrets/` (gitignored) so autoreloads don't orphan stored credentials.
`decrypt_key()` no longer swallows errors — it raises `InvalidToken` instead of returning
ciphertext that would be sent as a password.

Added `manage.py rotate_encryption_key --old-key <key>` (idempotent, `--dry-run` supported).
**Ran it on this database: 4 token values migrated, both connected mailboxes still work.**

> Those credentials were encrypted with a key that was public in the repo. They should still be
> revoked and reconnected at Google/Microsoft — the rotation only preserved continuity.

### 5. Prospecting · `integrations/apollo_service.py`, `leads/models.py`

Added the missing `Lead.title` field and fixed `icpScore` → `icp_score`. Added a
`MAX_LEADS_PER_SEARCH = 100` cap, tolerant count coercion, per-lead `IntegrityError` handling so a
duplicate doesn't kill the batch, and `logger` in place of silent failure. Autopilot sends now
route through the suppression gate.

> Before (live): `500 TypeError: Lead() got unexpected keyword arguments: 'title', 'icpScore'`
> After (live): `200 {"success":true,"fetched_count":3,"sandbox":true}`

### 6. Framework hardening · `richlead_backend/settings.py`, `urls.py`

- `DEFAULT_PERMISSION_CLASSES = IsAuthenticated` — deny by default
- Pagination (`PAGE_SIZE: 50`) and throttling (`anon` 30/min, `login` 10/min, `ai` 60/hr)
- `SECRET_KEY` required from env; `DEBUG` defaults to **False**
- `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` env-driven allowlists (was `['*']` / allow-all)
- HSTS, secure cookies, `X_FRAME_OPTIONS=DENY`, nosniff, proxy SSL header
- Login/refresh wrapped in throttled subclasses; added `/healthz/`

> Live: allowed origin gets `access-control-allow-origin`; `https://evil.example` gets nothing.

---

## P1

### 7. Dashboard metrics · `leads/models.py`, `leads/views.py`

Added `first_sent_at` / `replied_at` event timestamps, because a single mutable `status` field
cannot express "was sent **and** replied". `dashboard_stats` is now one `aggregate()` (was 7
separate `COUNT`s) keyed on timestamps. `messages_generated` now excludes empty drafts.
Migration `leads/0006` backfills historical rows from `status` + `created_at`.

> Before (live): 10 sent / 10 replied → `reply_rate: 0%`
> After (live): `{"messages_sent":10,"replies":10,"reply_rate":"100.0%"}`

### 8. Reply detection · `inbox/services.py`

`lead_emails` is now lowercased to match the already-lowercased inbound address (case mismatch was
silently dropping replies). Extracted `mark_replied()` and **added it to the IMAP path**, which
never had it — every SMTP tenant was stuck at a 0% reply rate.

### 9. Auth · `settings.py`, `users/serializers.py`, `app/lib/api.js`, `app/login/page.js`

Access token 30 days → **30 minutes**; refresh rotation + `token_blacklist` enabled so tokens are
actually revocable. Registration now enforces case-insensitive unique email.
Frontend gained `authFetch()` — attaches the bearer token, silently refreshes on 401, retries once,
and collapses concurrent refreshes into one round-trip.

> Live browser test: dead token → `401` → silent refresh → retry `200`.

---

## P2 / P3

### 10. Sending safety · `integrations/services.py`, `integrations/models.py`

- **Mock-send no longer lies.** With no connected mailbox the send now *fails*; sandbox is opt-in
  via `ALLOW_SANDBOX_SEND` and its response is flagged `"sandbox": true`.
  Previously it returned success and burned the lead to `reached` so it was never retried.
- **Daily send caps** per mailbox (`daily_send_limit`, default 50) with an auto-resetting counter,
  checked before any network call — Gmail ~500/day and Outlook ~300/day are hard limits.
- **Real rotation**: `pick_sending_account()` selects the least-loaded mailbox with quota left,
  replacing `accounts[lead.id % len(accounts)]` which ignored volume and reshuffled on deletion.

### 11. Unsubscribe · `integrations/unsubscribe.py` (new), `views.py`, `urls.py`

Signed (never-expiring, storage-free) tokens; `List-Unsubscribe` + `List-Unsubscribe-Post`
headers on SMTP and Gmail sends (RFC 8058, now required by Gmail/Yahoo for bulk senders); public
`/api/integrations/unsubscribe/<token>/` endpoint that suppresses the address and blacklists the lead.

> Live: valid token → `200` + suppressed + blacklisted. Tampered token → `400`.

### 12. Query budgets · `leads/views.py`, `inbox/views.py`

`LeadViewSet` gained `select_related('research')` + `prefetch_related(score_breakdowns, intent_signals)`;
`InboxListView` gained `select_related('lead')`. Both are now guarded by
`django_assert_max_num_queries` tests so regressions fail CI.

### 13. Dead endpoint · `ai_engine/urls.py`

`/api/ai/research-and-draft/` — called by the Leads page, previously **404** — is now routed.
AI generation is throttled at 60/hour per tenant.

### 14. Suppression UI · `app/suppression/page.js`

Replaced the hardcoded mock array with real API calls (list / create / delete), `@`-detection for
address-vs-domain, bulk paste, and error surfacing.

> Verified in browser: the page renders the entry created by the live unsubscribe test —
> proving the full loop email → unsubscribe → suppression → UI.

### 15. Logging · `oauth_views.py`, `settings.py`

Replaced `print()` calls that dumped full Graph profiles and decoded ID tokens with scrubbed
`logger` calls, plus a real `LOGGING` config.

---

## Regression found in testing (fixed)

**Deny-by-default broke the OAuth connect flow.** Adding
`DEFAULT_PERMISSION_CLASSES = IsAuthenticated` (fix #6) silently removed the implicit `AllowAny`
from `google_oauth_callback` and `microsoft_oauth_callback`. Providers redirect the user's browser
to those URLs with **no bearer token**, so the callback returned
`401 Authentication credentials were not provided` before ever reading the state.

This is precisely the landmine the review described in finding #7 — just pointed the other way:
turning the default on is correct, but every genuinely public endpoint must opt out *explicitly*.

- **Fix:** `@permission_classes([AllowAny])` on both callbacks, with a comment explaining that the
  single-use signed state carries the authorisation, not a session.
- **Why the test suite missed it:** `test_callback_with_forged_state_creates_no_account` asserted
  `status_code in (302, 401, 403)`. The 401 satisfied it. The assertion was too loose to
  distinguish "correctly rejected a forgery" from "endpoint is unreachable".
- **Now guarded by:**
  - `test_callback_is_reachable_without_authentication[google|microsoft]` — asserts `!= 401`
  - `test_callback_with_forged_state_redirects_with_error` — asserts `302` **and** `invalid_state`
  - `test_valid_state_passes_the_state_check` — asserts a real state is *not* rejected, so the gate
    can't pass by blocking everything
  - `test_every_api_view_declares_its_permissions` — scans the codebase and fails on any `@api_view`
    without explicit `permission_classes`, naming file and line

Verified by re-introducing the bug: 4 tests fail, including the audit test pointing at the exact line.

---

## Correction to the original review

**Finding #20 was wrong.** The review claimed `MAILERS` "is not a Django setting and does nothing".
In fact `MAILERS` **is** the Django 6.1+ setting and `EMAIL_BACKEND` is the deprecated one, removed
in Django 7.0. Django's own deprecation warning caught this. The original code was correct;
`MAILERS` is retained (now env-driven). CODE_REVIEW.md has been annotated.

---

## Not done — still open

These are from the review and remain outstanding. They are architectural rather than defects:

| # | Item | Why deferred |
|---|---|---|
| 15 | **Celery for async sends/syncs** | Sending is still synchronous in the request. Needs Redis + worker deployment — an infra decision, not a code change. |
| 16 | Warm-up ramp, bounce/complaint webhooks, auto-pause | Caps and rotation are in; the adaptive layer needs provider webhook endpoints. |
| 19 | **PostgreSQL migration** | Still SQLite. Will hit `database is locked` under concurrent load. |
| 21 | **Sequences page** | Still a UI mockup with no backend. Suggest removing from nav until built. |
| 25 | Multi-provider AI (Anthropic/Groq) | Still hardcoded to OpenAI `gpt-4o-mini`; other options silently fall back to mock. |
| 26 | Prompt-injection hardening | Lead fields still interpolated raw into the AI prompt. |
| 28 | CI, audit log, soft delete | Test suite now exists and is the prerequisite; CI wiring is next. |

A known lint warning (`react-hooks/set-state-in-effect`) remains on the suppression page — it is
the same fetch-on-mount pattern used by 5 other pages, kept for consistency rather than diverging.
