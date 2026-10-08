#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

APP_PATH=/opt/richlead-ip
RELEASE_SHA=${1:?usage: deploy-vps.sh RELEASE_SHA ARCHIVE_PATH}
ARCHIVE=${2:?usage: deploy-vps.sh RELEASE_SHA ARCHIVE_PATH}
[[ "$RELEASE_SHA" =~ ^[A-Fa-f0-9]{40}$ ]] || { echo "Invalid release id" >&2; exit 2; }
[[ "$ARCHIVE" == "/tmp/richlead-release-$RELEASE_SHA.tar.gz" ]] || {
  echo "Unexpected source archive path" >&2; exit 2;
}
[[ "$(id -un)" == richleadip ]] || { echo "Run this deploy as richleadip" >&2; exit 3; }
[[ -r "$APP_PATH/shared/runtime.env" ]] || { echo "RichLead runtime env is unavailable" >&2; exit 3; }
[[ -f "$ARCHIVE" ]] || { echo "Release archive is missing" >&2; exit 3; }

RELEASE="$APP_PATH/releases/$RELEASE_SHA"
CURRENT="$APP_PATH/current"
PREVIOUS=$(readlink -f "$CURRENT" 2>/dev/null || true)
ROLLBACK=0

rollback_on_failure() {
  status=$?
  if (( status != 0 && ROLLBACK )); then
    if [[ -n "$PREVIOUS" ]]; then
      ln -s "$PREVIOUS" "$APP_PATH/current.rollback"
      mv -Tf "$APP_PATH/current.rollback" "$CURRENT"
      sudo -n /usr/bin/systemctl restart richleadip-api.service richleadip-web.service || true
      echo "Deployment failed; previous RichLead release restored." >&2
    else
      echo "Deployment failed before any existing RichLead release could be restored." >&2
    fi
  fi
  rm -f -- "$ARCHIVE"
  exit "$status"
}
trap rollback_on_failure EXIT

mkdir -p "$RELEASE"
tar -xzf "$ARCHIVE" --no-same-owner -C "$RELEASE"
rm -f -- "$ARCHIVE"

# Reuse the active Python environment when the dependency manifest is unchanged.
if [[ -n "$PREVIOUS" && -f "$PREVIOUS/backend/requirements.txt" && \
      -x "$PREVIOUS/backend/.venv/bin/python" ]] && \
   [[ "$(sha256sum "$PREVIOUS/backend/requirements.txt" | cut -d' ' -f1)" == \
      "$(sha256sum "$RELEASE/backend/requirements.txt" | cut -d' ' -f1)" ]]; then
  ln -s "$(readlink -f "$PREVIOUS/backend/.venv")" "$RELEASE/backend/.venv"
else
  python3 -m venv "$RELEASE/backend/.venv"
  "$RELEASE/backend/.venv/bin/pip" install --disable-pip-version-check \
    -r "$RELEASE/backend/requirements.txt"
fi

cd "$RELEASE/backend"
eval "$(ENV_FILE="$APP_PATH/shared/runtime.env" .venv/bin/python -c 'import os, shlex; from dotenv import dotenv_values; values=dotenv_values(os.environ["ENV_FILE"]); [print("export " + key + "=" + shlex.quote(value)) for key, value in values.items() if value is not None]')"
[[ "${DEBUG,,}" == false ]] || { echo "DEBUG must be False" >&2; exit 3; }
[[ "${DATABASE_URL:-}" == postgres://* || "${DATABASE_URL:-}" == postgresql://* ]] || {
  echo "RichLead DATABASE_URL must use PostgreSQL" >&2; exit 3;
}

cd "$RELEASE"
npm ci --no-audit --no-fund
npm run build
npm prune --omit=dev --no-audit --no-fund

cd "$RELEASE/backend"
.venv/bin/python manage.py check --deploy
.venv/bin/python manage.py makemigrations --check --dry-run
mkdir -p "$APP_PATH/backups"
pg_dump --format=custom --no-owner --no-acl --dbname="$DATABASE_URL" \
  --file="$APP_PATH/backups/$RELEASE_SHA.dump"
chmod 600 "$APP_PATH/backups/$RELEASE_SHA.dump"
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput

ln -s "releases/$RELEASE_SHA" "$APP_PATH/current.next"
mv -Tf "$APP_PATH/current.next" "$CURRENT"
ROLLBACK=1
sudo -n /usr/bin/systemctl restart richleadip-api.service richleadip-web.service

HEALTHY=0
for attempt in {1..20}; do
  if curl --fail --silent --show-error --max-time 5 \
      --header 'Host: richlead.elevabel.com' \
      --header 'X-Forwarded-Proto: https' \
      http://127.0.0.1:8011/healthz/ >/dev/null && \
     curl --fail --silent --show-error --max-time 5 \
      https://richlead.elevabel.com/backend/healthz/ >/dev/null && \
     curl --fail --silent --show-error --max-time 5 \
      https://richlead.elevabel.com/senders >/dev/null; then
    HEALTHY=1
    break
  fi
  sleep 2
done

if (( ! HEALTHY )); then
  echo "RichLead post-deployment health check failed." >&2
  exit 5
fi

# Empty JSON bodies should reach Django validation (HTTP 400), not be redirected
# or downgraded to GET. These single probes do not create accounts or login.
LOGIN_PROBE_STATUS=$(curl --silent --show-error --max-time 5 --output /dev/null \
    --write-out '%{http_code}' --header 'Content-Type: application/json' \
    --data '{}' https://richlead.elevabel.com/backend/api/token/ || true)
SIGNUP_PROBE_STATUS=$(curl --silent --show-error --max-time 5 --output /dev/null \
    --write-out '%{http_code}' --header 'Content-Type: application/json' \
    --data '{}' https://richlead.elevabel.com/backend/api/users/register/ || true)
if [[ "$LOGIN_PROBE_STATUS" != 400 || "$SIGNUP_PROBE_STATUS" != 400 ]]; then
  echo "RichLead login/signup API method check failed (login=$LOGIN_PROBE_STATUS signup=$SIGNUP_PROBE_STATUS)." >&2
  exit 6
fi

ROLLBACK=0
echo "RichLead release $RELEASE_SHA deployed; API methods and health checks passed."
