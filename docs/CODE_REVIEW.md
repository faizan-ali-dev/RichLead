# RichLead — Senior Engineering Review

**Date:** 2026-09-26
**Scope:** Full stack — Django 6.1 backend (`backend/`), Next.js 16 frontend (`app/`, `components/`)
**Method:** Code read of every non-migration module + live testing against a running instance. Every finding marked **VERIFIED** was reproduced by executing it, not inferred.

---

## Verdict

This is a competent MVP prototype with a well-structured Django app layout and a polished UI. It is **not yet a SaaS**. The gap is not polish — it is that the core multi-tenant model, the compliance layer, and the sending pipeline have defects that would cause data loss, legal exposure, and mailbox bans in production.

Three things stand out as must-fix-before-any-customer:

1. A **global unique constraint on `Lead.email`** makes the product fundamentally single-tenant.
2. The **blacklist is not enforced and is silently erased** by the send path.
3. The **OAuth `state` parameter is forgeable**, allowing an attacker to bind a victim's mailbox to their own account.

---

## P0 — Blockers

### 1. `Lead.email` is globally unique → the app cannot support two customers · VERIFIED

`backend/leads/models.py:16`

```python
email = models.EmailField(unique=True)
```

The constraint is global, not per-user. Reproduced:

```
User A created lead shared@example.com  -> OK
User B created lead shared@example.com  -> IntegrityError: UNIQUE constraint failed: leads_lead.email
```

**Impact.** Any two customers prospecting the same market collide. The second customer simply cannot add the lead — and because `fetch_apollo_leads` does a bare `Lead.objects.create()`, their whole import crashes. This also leaks information: a customer can probe whether a competitor has already contacted someone.

**Fix.** Drop the global unique, scope it to the tenant:

```python
email = models.EmailField()          # no unique=True

class Meta:
    constraints = [
        models.UniqueConstraint(fields=["user", "email"], name="uniq_lead_email_per_user"),
    ]
    indexes = [models.Index(fields=["user", "status"])]
```

Needs a data migration to dedupe existing rows first.

---

### 2. Blacklisted leads are emailed, and the blacklist is destroyed · VERIFIED

`backend/integrations/services.py:7-61`

`send_outreach_email()` never checks `lead.status == 'blacklisted'`, and unconditionally sets `lead.status = 'reached'` on success. Reproduced:

```
lead.status = 'blacklisted'
send_outreach_email(...) -> {'success': True, 'message': 'Email sent (Sandbox Mode)'}
lead.status after send  -> 'reached'      # blacklist silently erased
```

**Impact.** This is the single worst bug in the codebase. A user who opted out gets emailed anyway, **and the record that they opted out is deleted**, so it will happen again on every subsequent run with no audit trail. Under GDPR Art. 21 and CAN-SPAM §5, a suppression request must be honoured permanently. This is direct legal exposure, not a technical nit.

**Fix.** Guard at the top of the send path, and never let status regress:

```python
if lead.status == 'blacklisted':
    return {"success": False, "error": "Lead is suppressed."}
if SuppressionEntry.objects.filter(user=user, email__iexact=lead.email).exists():
    return {"success": False, "error": "Email is on the suppression list."}
```

Model status as a state machine where `blacklisted` and `replied` are terminal with respect to `reached`.

---

### 3. OAuth `state` is unsigned and forgeable → mailbox hijack · VERIFIED

`backend/integrations/oauth_views.py:21-22, 54-55, 115-116, 155-156`

```python
state_data = json.dumps({"user_id": request.user.id})
state = base64.urlsafe_b64encode(state_data.encode()).decode()
```

The callback base64-decodes this and trusts `user_id` with no signature, no nonce, and no server-side lookup. `{"user_id": 1}` encodes to `eyJ1c2VyX2lkIjogMX0=` — anyone can produce it.

**Two attacks, both serious:**

- **Mailbox theft.** Attacker sends a victim an OAuth init link carrying `state` = *attacker's* user_id. Victim consents with their own Google account. The victim's access + refresh tokens are stored on the **attacker's** `EmailAccount` row. The attacker now has `https://mail.google.com/` scope — full read and send on the victim's mailbox.
- **Mailbox injection.** Attacker connects their own mailbox with `state` = victim's user_id, planting a sender account inside the victim's tenant.

Both callbacks are also unauthenticated (correctly — but that is precisely why `state` must carry the trust).

**Fix.** `state` must be an opaque, single-use, server-side value:

```python
state = secrets.token_urlsafe(32)
cache.set(f"oauth_state:{state}", {"user_id": request.user.id}, timeout=600)
# callback:
data = cache.get(f"oauth_state:{state}")
if not data:
    return redirect(f"{frontend_url}?error=invalid_state")
cache.delete(f"oauth_state:{state}")   # single use
```

Also add PKCE, and never derive identity from anything in the redirect URL.

---

### 4. Encryption key is hardcoded in source · VERIFIED by inspection

`backend/integrations/models.py:8`

```python
_static_key = getattr(settings, 'FERNET_KEY', b'<a hardcoded 32-byte key, redacted>')
```

`FERNET_KEY` is **not defined anywhere in `settings.py`**, so this fallback is what actually runs. Every customer's OpenAI/Apollo API keys, SMTP passwords, and Google/Microsoft refresh tokens are encrypted with a key committed to Git.

**Impact.** The encryption is decorative. Anyone with the repo and a DB dump decrypts everything. Rotating it is not enough — assume every credential ever stored is compromised and force re-entry.

Two aggravating details in the same file:

```python
except:                       # line 11, 22 — bare except
    return encrypted_key      # line 23 — returns CIPHERTEXT on failure
```

`decrypt_key` returning the raw ciphertext when decryption fails means a key-rotation bug silently sends base64 garbage as an SMTP password instead of erroring.

**Fix.** Load from env, fail loudly if absent, and let decryption errors raise:

```python
FERNET_KEY = os.environ["FERNET_KEY"]        # settings.py — no default
```

Consider envelope encryption (KMS) so per-tenant keys can be rotated independently.

---

### 5. Prospecting is completely broken · VERIFIED

`backend/integrations/apollo_service.py:41-50`

```python
Lead.objects.create(user=user, ..., title=data['title'], icpScore=random.randint(70,99), ...)
```

`Lead` has neither field — the column is `icp_score`, and `title` does not exist. Live call:

```
POST /api/integrations/apollo-search/
-> 500  TypeError: Lead() got unexpected keyword arguments: 'title', 'icpScore'
```

**Impact.** The headline feature of the product — go find me leads — throws a 500 on every call. This has clearly never been executed once. It strongly suggests there is **no test suite and no CI**: all four `tests.py` files are the untouched 3-line Django stubs.

**Fix.** Add a `title` field to `Lead`, use `icp_score`, and add a smoke test that actually calls the endpoint. Then wire real Apollo (`apollo_service.py` currently ignores `api_key` entirely and always returns `random.randint` mock data — worth being explicit with users that Prospecting is sandbox-only today).

---

## P1 — Security & correctness

### 6. Dashboard reply rate is mathematically wrong · VERIFIED

`backend/leads/views.py:27-30`

```python
messages_sent = user_leads.filter(status='reached').count()
replies       = user_leads.filter(status='replied').count()
reply_rate    = round((replies / messages_sent * 100) if messages_sent > 0 else 0, 1)
```

`status` is a single field, so a lead that replies **leaves** the `reached` bucket. The denominator excludes exactly the successes it is measuring. Reproduced:

```
10 emailed, all 10 replied -> messages_sent=0, replies=10 -> reply_rate = 0.0%   (should be 100%)
 8 reached,  2 replied     -> reply_rate = 25.0%                  (should be 20%)
```

The metric is *always* wrong and gets worse as the product works better — the best possible outcome reports 0%.

**Fix.** Separate lifecycle state from events. Add `first_sent_at` / `replied_at` timestamps (or count `EmailMessage` rows by direction) and compute:

```python
sent    = user_leads.filter(first_sent_at__isnull=False).count()
replied = user_leads.filter(replied_at__isnull=False).count()
```

Related: `messages_generated` (line 25) filters `research__generated_message__isnull=False`, but the field is non-nullable — an empty string is not NULL, so this just counts rows with research. Use `.exclude(research__generated_message='')`.

### 7. No `DEFAULT_PERMISSION_CLASSES` → endpoints are public by default

`settings.py:67-71` sets only authentication, not permissions. DRF's default is `AllowAny`, so **any view where someone forgets `@permission_classes` is world-readable**. That is a landmine, and the OAuth callbacks already rely on it.

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_THROTTLE_RATES': {'anon': '20/min', 'user': '1000/day'},
}
```

Then opt specific views out with `@permission_classes([AllowAny])`.

### 8. No rate limiting on login — brute force is free · VERIFIED

8 consecutive bad-password POSTs to `/api/token/`: `401 401 401 401 401 401 401 401`. No lockout, no delay, no throttle. Add `ScopedRateThrottle` on the token endpoint and `django-axes` for account lockout.

### 9. 30-day access tokens in `localStorage`, no refresh, no revocation

`settings.py:165-169` + `app/login/page.js:31`

```python
'ACCESS_TOKEN_LIFETIME': timedelta(days=30)
'ROTATE_REFRESH_TOKENS': False
```

```js
localStorage.setItem("richlead_token", data.access);   // refresh token discarded
```

Three compounding problems:

- A 30-day **access** token cannot be revoked (no blacklist app installed). Logout is cosmetic; a stolen token is valid for a month.
- `localStorage` is readable by any XSS. Given the app renders AI-generated and email-derived content, XSS is a live risk.
- The refresh token is thrown away, so `/api/token/refresh/` is dead code and users are hard-logged-out after 30 days.

**Fix.** 15-minute access token, refresh token in an `HttpOnly; Secure; SameSite=Strict` cookie, enable `rest_framework_simplejwt.token_blacklist`, rotate on refresh.

### 10. Production-unsafe settings

`settings.py`:

| Line | Setting | Issue |
|---|---|---|
| 27 | `SECRET_KEY` | insecure `django-insecure-…` fallback baked in — if `.env` is missing, sessions/tokens are forgeable |
| 30 | `DEBUG` | defaults to `True`; full tracebacks with source shipped to clients (confirmed on the Apollo 500) |
| 32 | `ALLOWED_HOSTS = ['*']` | Host-header injection |
| 145 | `CORS_ALLOW_ALL_ORIGINS = True` | any site can call the API with a user's token |

Make `SECRET_KEY` and `FERNET_KEY` required (`os.environ[...]`), default `DEBUG` to `False`, and use `CORS_ALLOWED_ORIGINS = [...]`.

### 11. Duplicate emails on registration · VERIFIED

`users/serializers.py` validates the password but not email uniqueness (`AbstractUser.email` is not unique). Two accounts registered with `dup@example.com` — both `HTTP 201`. Makes password reset ambiguous and enables account-confusion. Add a `UniqueValidator` on email and an `EmailField(unique=True)` on the model.

### 12. Cross-tenant message loss in the inbox

`inbox/models.py:11` — `message_id = models.CharField(unique=True)` (global), and the sync guards are `EmailMessage.objects.filter(message_id=...).exists()` with **no user filter** (`inbox/services.py:98, 182, 270`).

If two customers are on the same thread, whoever syncs first claims the ID and the second customer **silently never receives the message**. Same fix as `Lead.email`: `UniqueConstraint(fields=["user", "message_id"])` and add `user=user` to every dedupe query.

### 13. Reply detection is case-sensitive and missing for IMAP

- `inbox/services.py:19` builds `lead_emails` from raw DB values; line 46 lowercases the incoming address before comparing. A lead stored as `Alice@Corp.com` never matches a reply from `alice@corp.com` — the reply is dropped. Normalize emails on save (lowercase) and compare on the normalized column.
- `_sync_imap` never sets `lead.status = 'replied'` — only the Graph (line 222) and Gmail (line 342) paths do. **Every SMTP/IMAP customer has a permanently 0% reply rate.**

### 14. Secrets and PII in stdout logs

`oauth_views.py:200` prints the full Microsoft Graph profile; `:218` prints the decoded ID token; `services.py` prints matched lead emails and full mock email bodies. In any hosted environment these land in log aggregation. Replace `print()` with the `logging` module and scrub tokens/PII.

---

## P2 — Architecture & scale

### 15. Email sending is synchronous inside the HTTP request

`integrations/views.py:34` → `send_outreach_email()` does SMTP connect/login/send (or Graph/Gmail HTTP) **in the request cycle**. `fetch_apollo_leads` goes further and loops `count` times doing an OpenAI call *and* a send per lead (`apollo_service.py:58-64`) — a 100-lead import is ~200 sequential network round-trips inside one request. It will time out behind any reverse proxy, and a partial failure leaves leads half-processed with no retry.

**Fix.** Celery (or Django-Q/RQ) + Redis. Endpoints enqueue and return a job id; the worker owns retries with exponential backoff and idempotency keys.

### 16. No sending limits, warm-up, or throttling — mailboxes will get banned

There is no per-account daily cap, no inter-send delay, no ramp-up schedule, and no bounce handling. Gmail (~500/day) and Outlook (~300/day) enforce hard limits, and cold-outreach patterns trip spam heuristics fast. A user who imports 1,000 leads with Autopilot on will get their mailbox suspended on day one — and because sending is synchronous, they will hit it in a single request.

This is table stakes for the category. Needs: per-`EmailAccount` daily counters, configurable caps, randomized delays, warm-up ramp, bounce/complaint webhooks, and auto-pause on bounce-rate threshold.

### 17. Account rotation isn't rotation

`integrations/services.py:23`

```python
email_account = connected_accounts[lead.id % len(connected_accounts)]
```

Keyed on `lead.id` rather than send volume, so distribution follows whatever gaps exist in lead IDs, and **deleting one account reshuffles every future assignment** — breaking thread continuity, since a follow-up can go out from a different mailbox than the original. Track `sends_today` per account and pick least-loaded; pin a lead to its account for the life of the thread.

### 18. N+1 queries and no pagination

- `InboxListView` (`inbox/views.py:16-36`) loads **all** messages, touches `msg.lead.*` per row (N+1), serializes one at a time, and groups in Python. Add `.select_related('lead')` and paginate.
- `LeadViewSet` returns a bare array — confirmed no pagination envelope. `LeadSerializer` hits `score_breakdowns`, `intent_signals`, and `research` per lead (4 queries × N). Add `prefetch_related`.
- `dashboard_stats` runs 7 separate `COUNT` queries; collapse into one `aggregate()`.

### 19. SQLite in a write-heavy multi-tenant app

`settings.py:107-112`. SQLite single-writer locking will produce `database is locked` under concurrent syncs and sends. Move to PostgreSQL before any real traffic.

### 20. Dead and duplicated code

- ~~`MAILERS` (`settings.py:156`) is not a Django setting — it does nothing.~~ **Correction: this finding was wrong.** `MAILERS` *is* the Django 6.1+ setting; `EMAIL_BACKEND` is the deprecated one and is removed in Django 7.0. The original code was correct.
- Imports scattered mid-file (`services.py:31, 64, 93, 119`; `views.py:19, 41`; `users/views.py:24`) — move to module top.
- Token-refresh logic is copy-pasted four times across `integrations/services.py` and `inbox/services.py`. Extract one `EmailAccount.ensure_fresh_token()`.
- `token_expiry` exists on the model but is **never written** — refresh is purely reactive to a 401, costing a wasted round-trip on every expired call.

---

## P3 — Product & feature gaps

### 21. Two navigation items are non-functional mockups · VERIFIED

| Page | Backend | Reality |
|---|---|---|
| `app/sequences/page.js` | none | `useState` array of hardcoded steps. Multi-step sequences do not exist. |
| `app/suppression/page.js` | none | No model, no endpoint. **The compliance feature is a UI shell.** |

Suppression being fake is the dangerous one — it visually promises the exact guarantee that finding #2 shows the backend actively violates. Either build it (a `SuppressionEntry` model checked in the send path, plus domain-level suppression) or remove it from the nav until it is real.

### 22. Frontend calls an endpoint that doesn't exist · VERIFIED

`app/leads/page.js:126` posts to `/api/ai/research-and-draft/` → **404** (only `process-lead/` and `prompts/` are registered). The "research and draft" action on the Leads page is dead.

### 23. No unsubscribe mechanism anywhere

No unsubscribe link, no List-Unsubscribe header, no physical address in outbound mail. CAN-SPAM §5 requires all three for commercial email; GDPR requires a lawful basis and an easy objection route. Combined with #2 and #21, the product currently has **no working opt-out path at all**. Add a signed unsubscribe URL, the `List-Unsubscribe` / `List-Unsubscribe-Post` headers, and a tenant-level footer with postal address.

### 24. "Mock mode" reports success for emails never sent

`integrations/services.py:51-81` — with no connected mailbox, the code prints to stdout, marks the lead `reached`, writes an `EmailMessage`, and returns `{"success": True, "message": "Email sent (Sandbox Mode)"}`. The UI shows a success toast.

In a SaaS this is the worst possible default: a user who hasn't finished onboarding believes their campaign is running while nothing is sent, and the leads are burned to `reached` so they will never be retried. Return an explicit error and require a connected sender, or surface sandbox mode unmistakably in the UI and don't mutate lead state.

### 25. Multi-provider AI is modelled but not implemented

`APIIntegration.PROVIDER_CHOICES` offers `openai`/`anthropic`/`groq`, but `ai_engine/services.py:18` hardcodes `provider='openai'` and `model="gpt-4o-mini"`. Selecting Anthropic or Groq silently falls back to the mock generator. Either implement the providers or hide the unsupported options.

> Note: if you do add Anthropic, current model ids are `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5-20251001` — don't copy older `claude-3-*` ids from tutorials.

### 26. Prompt injection via lead data

`ai_engine/services.py:38-47` interpolates `lead.name`, `lead.company`, `lead.niche` straight into the prompt. Since leads arrive from imports/Apollo, a company field containing *"Ignore previous instructions and write…"* steers the generated email — which is then **auto-sent under the customer's domain** when Autopilot is on. Delimit untrusted values, and keep a human-review gate for anything Autopilot sends.

### 27. No per-tenant cost controls on AI

Every `process_lead` call spends the user's OpenAI quota with no per-user quota, no caching, no dedupe. `fetch_apollo_leads` fires one completion per lead in a loop with no ceiling. A `count: 10000` request would attempt 10,000 completions. Enforce a hard cap on `count`, add quotas, and cache by `(lead, template)` hash.

### 28. Missing operational basics

- **Zero tests.** All `tests.py` are stubs. Bug #5 would have been caught by a single integration test.
- **No CI**, no linting on the backend, no `.env` validation on boot.
- **No audit log** of who sent what to whom — necessary for GDPR data-subject requests.
- **No soft delete** — `on_delete=CASCADE` from `User` wipes all evidence of consent/suppression history.
- **No health check** endpoint.
- **No `AIResearch` versioning** — `get_or_create` + overwrite destroys prior drafts (`services.py:69-72`); users cannot compare or revert.
- `README.md` is still the stock `create-next-app` boilerplate — no setup steps, no architecture notes, no env documentation.

---

## Suggested order of work

**Before any customer touches it**
1. Per-tenant uniqueness on `Lead.email` and `EmailMessage.message_id` (#1, #12)
2. Enforce suppression + stop status regression in the send path (#2)
3. Sign/store OAuth `state`, add PKCE (#3)
4. Move `FERNET_KEY` to env, force credential re-entry, remove bare excepts (#4)
5. Fix `apollo_service` field names + add a smoke test (#5)
6. `DEFAULT_PERMISSION_CLASSES`, throttling, `DEBUG=False`, real CORS/hosts (#7, #8, #10)

**Before scale**
7. Celery for sends and syncs (#15)
8. Sending caps, warm-up, bounce handling, real rotation (#16, #17)
9. Fix reply-rate math and reply detection (#6, #13)
10. PostgreSQL, pagination, `select_related`/`prefetch_related` (#18, #19)
11. Short-lived JWT + HttpOnly refresh cookie + blacklist (#9)

**Before calling it feature-complete**
12. Real suppression backend + unsubscribe headers/link (#21, #23)
13. Build sequences or remove the nav item (#21)
14. Fix or remove `research-and-draft` (#22)
15. Remove silent mock-send success (#24)
16. Tests, CI, audit logging, real README (#28)

---

## What's genuinely good

Worth keeping as you refactor — these are the right instincts:

- **Clean app boundaries.** `users` / `leads` / `integrations` / `ai_engine` / `inbox` split along real domain lines, not technical layers. This is why the fixes above are mostly localized.
- **Tenant scoping via `get_queryset()`** is applied consistently across all four ViewSets — the pattern is right, it's the DB constraints that betray it.
- **Credential encryption at the model layer** with `set_*`/`get_*` accessors is the correct shape; only the key management is wrong.
- **Deliverability awareness** — the anti-spam system prompt, dash stripping, `Message-ID`/`Date` headers, display-name derivation, and junk-folder checking show real domain knowledge.
- **Reactive token refresh with retry** on both providers is more than most MVPs bother with.
- The `EmailMessage.direction` model is a sound foundation for real threading.
