# RichLead Ubuntu VPS deployment

This repository prepares a single-host HTTPS deployment for the Next.js UI, Django API/admin, PostgreSQL, and static admin assets. Browser API requests use the same HTTPS origin by default; the UI has no baked-in localhost API address. The backend accepts `DATABASE_URL=postgresql://...` and requires PostgreSQL in the production deployment script.

No server, database, domain, credentials, GitHub secrets, or CI deployment has been provisioned or tested here. Before enabling the workflow, you need the VPS hostname, public domain, SSH account/key, installation path, PostgreSQL database/user/password, OAuth app credentials if mailbox OAuth is desired, and generated Django/Fernet secrets.

## GitHub Actions

`.github/workflows/production.yml` runs on every push to `main`. It installs backend test dependencies, runs pytest, Django deployment checks and migration checks, and builds the frontend. It only deploys a push event on `main`, after all verification passes. `workflow_dispatch` runs verification and does not deploy.

Create a GitHub Actions **production environment** and configure these secrets there:

| Secret | Value |
|---|---|
| `VPS_HOST` | VPS DNS name or IP address |
| `VPS_USER` | Dedicated non-root deployment account on the VPS |
| `VPS_SSH_PRIVATE_KEY` | Private SSH deployment key, including begin/end lines |
| `VPS_SSH_KNOWN_HOSTS` | VPS host-key line, verified through the VPS console/provider; do not trust an unverified `ssh-keyscan` result |
| `VPS_APP_PATH` | Absolute installation path; default `/opt/richlead` |
| `PRODUCTION_ENV_FILE` | Complete systemd-compatible environment file contents, detailed below; multiline secret |

Optionally set the non-secret GitHub Actions **production environment variable** `NEXT_PUBLIC_API_BASE` to an HTTPS API origin at build time. Leave it unset for the recommended same-origin Nginx route. Frontend `NEXT_PUBLIC_` values are compiled during verification; changing this variable requires a new deployment build.

Add the matching public SSH key to `VPS_USER`'s `authorized_keys`. Restrict that account to the RichLead directory and the required service restart commands where practical. The included deploy helper uses `sudo systemctl restart/stop richlead-api richlead-web`. Install the matching service files so their paths agree with `VPS_APP_PATH`; the supplied examples use `/opt/richlead`. GitHub Actions are pinned to immutable commit SHAs; update these pins through review when upgrading the actions.

GitHub environment values are intentionally empty until the operator supplies them. No host, password, private key, or customer data is in the workflow.

## VPS prerequisites

Use a supported Ubuntu LTS VPS. Provision the domain and DNS A/AAAA records to point to it. Before enabling the GitHub workflow, install and configure:

- Nginx, Certbot with its Nginx plugin, Git, rsync, curl, and OpenSSH server.
- Python 3.12 plus `python3.12-venv`; Node.js 22 LTS plus npm; PostgreSQL server/client tools including `pg_dump`.
- A `richlead` service account with no interactive login, an SSH deployment account with write access to the app path, and an operator with narrowly scoped passwordless systemctl permissions for the two named services.
- Add the deployment account to the `richlead` group. Set the shared directory group to `richlead` with setgid permissions so the deployment helper can write secrets readable only by the service group.
- The provided `richlead-api.service` and `richlead-web.service`, installed as `/etc/systemd/system/` units and adjusted to match the installation path if it differs from `/opt/richlead`.
- The provided Nginx site as a starting configuration, with `server_name` set to the chosen public domain and its static alias matched to the install path.
- The supplied `/etc/nginx/conf.d/richlead-limits.conf` rate-limit zones and the matching Nginx site. Login/refresh requests are limited to 10 per minute per source IP (with a short burst); signup is limited to 3 per minute. These Nginx limits are shared across Gunicorn workers; Django's per-process DRF throttles remain a secondary guard.
- A PostgreSQL database and least-privilege login created by the VPS operator. The deploy job does not create, change, or guess the database. Put the final connection URL in the GitHub environment secret only after testing it on the VPS.

Expose ports 80/443 publicly. Keep PostgreSQL listening on loopback/private interfaces; firewall PostgreSQL (5432), Gunicorn (8000), and Next.js (3000) from public ingress. SMTP/IMAP outbound access must be restricted at the VPS firewall/cloud layer too; application-side DNS/IP filtering is defense in depth.

If a trusted CDN or load balancer sits in front of Nginx, configure `real_ip_header` and `set_real_ip_from` only for its published IP ranges before relying on source-IP limits. Never trust arbitrary client-supplied `X-Forwarded-For` values.

## PostgreSQL provisioning and operator backup

Create a database and dedicated login through the VPS's PostgreSQL administrative account. Substitute unique credentials locally; do not paste them into a commit or this document:

```sql
CREATE ROLE richlead LOGIN PASSWORD 'replace-with-a-unique-password';
CREATE DATABASE richlead OWNER richlead ENCODING 'UTF8';
```

Set a percent-encoded URL such as `postgresql://richlead:URL_ENCODED_PASSWORD@127.0.0.1:5432/richlead`. `DATABASE_SSLMODE` defaults to `require`; PostgreSQL must support TLS for that setting. For a database intentionally bound only to loopback on the same VPS, an operator may set `DATABASE_SSLMODE=disable`. Do not disable TLS for a database connection crossing a network.

Before first deploy, restore-test a `pg_dump --format=custom` backup. Each deployment takes a protected dump under `<APP_PATH>/backups/` before applying migrations; retention, off-server copies, disk monitoring, and restore drills remain the operator's responsibility. Application migrations must remain backwards compatible with the currently running release to support rollback after a health-check failure.

## Production environment file

Create the file value for `PRODUCTION_ENV_FILE` with one `NAME=value` entry per line and no shell commands. Do not put quotes around values unless systemd dotenv parsing has been checked. Percent-encode reserved characters in database URL credentials. Generate unique values for both Django secrets. Never use the example placeholders as real values.

```dotenv
DEBUG=False
SECRET_KEY=GENERATE_A_UNIQUE_DJANGO_SECRET
FERNET_KEY=GENERATE_WITH_cryptography_fernet_Fernet_generate_key
ALLOWED_HOSTS=app.example.com
CORS_ALLOWED_ORIGINS=https://app.example.com
CSRF_TRUSTED_ORIGINS=https://app.example.com
BACKEND_URL=https://app.example.com
FRONTEND_URL=https://app.example.com
DATABASE_URL=postgresql://richlead:URL_ENCODED_PASSWORD@127.0.0.1:5432/richlead
DATABASE_SSLMODE=require
GOOGLE_CLIENT_ID=optional-google-client-id
GOOGLE_CLIENT_SECRET=optional-google-client-secret
MICROSOFT_CLIENT_ID=optional-microsoft-client-id
MICROSOFT_CLIENT_SECRET=optional-microsoft-client-secret
MICROSOFT_TENANT_ID=common
ALLOW_SANDBOX_SEND=False
NEXT_PUBLIC_API_BASE=
```

Use the same HTTPS origin for the frontend and Django paths unless you intentionally set `NEXT_PUBLIC_API_BASE` and configure CORS, cookie, OAuth callback, TLS, and reverse-proxy behavior for a separate API origin. The simplest supported layout is one domain with Nginx routing `/api/`, `/admin/`, and `/static/` to Django and other paths to Next.js. OAuth must use the exact callback URL under this domain in each provider console. Do not store an API origin pointing at localhost in production.

The deployed `richlead` service account must be able to read the generated secret file. Keep it outside the public web root with owner-only deployment access and service-group read access; the deployment helper sets the file to `0640` and its parent directory to `0750`. Django's `BASE_DIR` is `backend/`, so collected static files live under `backend/staticfiles/` in each release.

## Initial server setup

1. Set up DNS, Ubuntu packages, PostgreSQL, the least-privilege database, service accounts, and firewall rules. Test `pg_dump` and a secure database connection before the first release.
2. Create `<APP_PATH>/releases`, `<APP_PATH>/shared`, and `<APP_PATH>/backups`. Ensure deployment/service accounts have the needed ownership and permissions. For the default path, a starting layout is `sudo install -d -o VPS_USER -g richlead -m 2770 /opt/richlead /opt/richlead/releases /opt/richlead/shared`; keep backups owner-only for `VPS_USER`.
3. Install the two supplied systemd unit files. Update each hardcoded `/opt/richlead` to match `VPS_APP_PATH` if you chose another path. Install `nginx-richlead-limits.conf` under `/etc/nginx/conf.d/`. Enable the Nginx site using the supplied template with the real hostname, validate it with `nginx -t`, and reload Nginx.
4. Add the GitHub secrets above; create a first superuser after deployment using the new release's Python environment and production environment.
5. Configure HTTPS using Certbot after DNS resolves and the HTTP Nginx site is reachable. Check redirects, admin static assets, `/healthz/`, login/signup, OAuth callback registration, and logs.
6. Protect `main` with required CI checks/review and restrict write access. Only then will pushing to `main` deploy to the VPS.

## Deployment behavior, recovery, and limitations

The workflow uploads an immutable commit-named release without copying local secrets, virtual environments, or node modules. It installs the pinned backend dependencies, requires `DEBUG=False` and a PostgreSQL `DATABASE_URL`, saves a database dump, migrates, collects static files and runs `check --deploy`. It transfers the frontend build produced by CI, installs production Node dependencies, atomically switches the `current` symlink, restarts both services and probes Django through its loopback-only Gunicorn listener. A failed post-switch health probe switches `current` back and restarts the old release. Failed verification never starts deployment. Check GitHub Actions and `journalctl -u richlead-api -u richlead-web` for results.

The schema migration and code switch cannot be one transaction across PostgreSQL and files. Keep migrations additive/backwards compatible; take and retain the pre-migration database dump. For an unrecoverable schema issue, restore that dump during a maintenance window and point `current` to the previous release. Keep old releases until the new release has been observed stable; clean old releases and backups according to an explicit retention policy.

There is no configured job queue or worker service, object-storage backup, rate-limit cache, email delivery service, uptime monitor, or database maintenance automation yet. This VPS setup is a deployable baseline, not a complete managed SaaS operating plan. The test job uses SQLite for speed; run staging against the actual PostgreSQL version before the first production data migration.
