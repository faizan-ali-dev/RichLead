# Background workers

RichLead stores job state, idempotency keys, and an outbox record in PostgreSQL. Celery uses Redis only to deliver work; it is not the result database. The API, worker, and one Beat scheduler must use the same `DATABASE_URL` and `CELERY_BROKER_URL` from `/opt/richlead-ip/shared/runtime.env`. Beat re-dispatches queued outbox rows after an interrupted API publish; worker task guards prevent duplicate external actions.

## Production prerequisites

- Install and start a local Redis service. Keep it bound to loopback or a private network, require authentication if it is reachable beyond loopback, and enable Redis persistence (AOF) so queued messages survive a host restart.
- Set `CELERY_BROKER_URL` in the shared runtime env to the private Redis URL. Do not use the example credentials or expose Redis publicly.
- Install `backend/deploy/richleadip-celery-worker.service` and `backend/deploy/richleadip-celery-beat.service` as systemd units. These units run under the existing `richleadip` account, follow `/opt/richlead-ip/current`, and use the same release virtualenv as the API.
- Ensure only one Beat service runs. Worker concurrency defaults to two; increase it only after checking available memory and provider/mailbox rate limits.

After Redis and both units are provisioned, run Django migrations with the normal RichLead release and start the units:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now richleadip-celery-worker.service richleadip-celery-beat.service
sudo systemctl status richleadip-celery-worker.service richleadip-celery-beat.service
```

Check worker and scheduler logs with `journalctl -u richleadip-celery-worker -u richleadip-celery-beat`. The web UI submits long-running work to `/api/jobs/<id>/` and polls its owner-scoped database status. If Redis or the worker is unavailable, the API returns a service-unavailable response instead of running provider, email, or mailbox work inside the web request.

Email sends and provider searches are deliberately not retried automatically after ambiguous worker loss: repeating an external operation could send duplicates or spend provider credits twice. Verify the mailbox/provider before manually retrying a job marked uncertain.
