# Background workers

RichLead stores job state, idempotency keys, and an outbox record in PostgreSQL. Celery uses Redis only to deliver work; it is not the result database. The API, worker, and one Beat scheduler must use the same `DATABASE_URL` and `CELERY_BROKER_URL` from `/opt/richlead-ip/shared/runtime.env`. Beat re-dispatches queued outbox rows after an interrupted API publish; worker task guards prevent duplicate external actions.

## Production prerequisites

- Install and start a local Redis service. Keep it bound to loopback or a private network, require authentication if it is reachable beyond loopback, and enable Redis persistence (AOF) so queued messages survive a host restart.
- Set `CELERY_BROKER_URL` in the shared runtime env to the private Redis URL. Do not use the example credentials or expose Redis publicly.
- Install `backend/deploy/richleadip-celery-worker.service` and `backend/deploy/richleadip-celery-beat.service` as systemd units. These units run under the existing `richleadip` account, follow `/opt/richlead-ip/current`, and use the same release virtualenv as the API. Keep Beat's schedule in its own writable subdirectory so the scheduler never needs write access to the shared secrets directory.
- Ensure only one Beat service runs. Worker concurrency defaults to two; increase it only after checking available memory and provider/mailbox rate limits.

After Redis and both units are provisioned, run Django migrations with the normal RichLead release and start the units:

```sh
sudo systemctl daemon-reload
sudo install -d -o richleadip -g richleadip -m 0750 /opt/richlead-ip/shared/celery
sudo systemctl enable --now richleadip-celery-worker.service richleadip-celery-beat.service
sudo systemctl status richleadip-celery-worker.service richleadip-celery-beat.service
```

Check worker and scheduler logs with `journalctl -u richleadip-celery-worker -u richleadip-celery-beat`. The web UI submits long-running work to `/api/jobs/<id>/` and polls its owner-scoped database status. If Redis or the worker is unavailable, the API returns a service-unavailable response instead of running provider, email, or mailbox work inside the web request.

Email sends and provider searches are deliberately not retried automatically after ambiguous worker loss: repeating an external operation could send duplicates or spend provider credits twice. Verify the mailbox/provider before manually retrying a job marked uncertain.

## Redis cache

Django uses a Redis cache on logical database 1 by default in production; Celery keeps using the broker URL, normally logical database 0. Set `REDIS_CACHE_URL` to a dedicated private Redis endpoint when cache memory/eviction must be isolated from the job broker. Do not expose Redis publicly.

Caching can be controlled without a code change through the shared runtime environment:

- `CACHE_ENABLED=False` bypasses all cache lookups and writes.
- Set any individual TTL to `0` to disable that cache: `CACHE_DASHBOARD_STATS_TTL`, `CACHE_APOLLO_PREVIEW_TTL`, `CACHE_HUNTER_PREVIEW_TTL`, or `CACHE_PROVIDER_METADATA_TTL`.
- Dashboard stats default to 20 seconds; Apollo and Hunter company previews to 120 seconds; static LLM provider metadata to 24 hours.

The dashboard summary is tenant-scoped and invalidated after committed model writes. Apollo/Hunter caches are limited to company previews and include the tenant, request data, and a digest of its API key in the cache key. Contact enrichment, lead imports, mailbox data, and email sends are not cached. Cache connection errors fall back to fresh data from the source rather than failing the request.
