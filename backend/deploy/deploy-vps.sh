#!/usr/bin/env bash
set -Eeuo pipefail

APP_PATH=${1:?usage: deploy-vps.sh APP_PATH RELEASE_SHA}
RELEASE_SHA=${2:?usage: deploy-vps.sh APP_PATH RELEASE_SHA}
[[ "$APP_PATH" =~ ^/[A-Za-z0-9_./-]+$ && "$APP_PATH" != / && "$APP_PATH" != *"/../"* && "$APP_PATH" != */.. ]] || {
  echo "APP_PATH must be a safe absolute path" >&2; exit 2;
}
[[ "$RELEASE_SHA" =~ ^[A-Fa-f0-9]{7,64}$ ]] || { echo "Invalid release id" >&2; exit 2; }

RELEASE="$APP_PATH/releases/$RELEASE_SHA"
CURRENT="$APP_PATH/current"
PREVIOUS=$(readlink "$CURRENT" 2>/dev/null || true)
ROLLBACK=0

rollback_on_failure() {
  status=$?
  if (( status != 0 && ROLLBACK )); then
    if [[ -n "$PREVIOUS" ]]; then
      ln -sfn "$PREVIOUS" "$APP_PATH/current.rollback"
      mv -Tf "$APP_PATH/current.rollback" "$CURRENT"
      sudo systemctl restart richlead-api richlead-web || true
      echo "Deployment failed; restored previous release $PREVIOUS" >&2
    else
      rm -f "$CURRENT"
      sudo systemctl stop richlead-api richlead-web || true
      echo "Initial deployment failed; services stopped" >&2
    fi
  fi
  exit "$status"
}
trap rollback_on_failure EXIT

cd "$RELEASE/backend"
python3 -m venv .venv
.venv/bin/pip install --disable-pip-version-check -r requirements.txt

test -f "$APP_PATH/shared/.env"
chmod 600 "$APP_PATH/shared/.env"
# Parse the operator-managed dotenv file using the same parser Django uses.
# Shell quoting prevents keys/values from being executed as shell syntax.
eval "$(ENV_FILE="$APP_PATH/shared/.env" .venv/bin/python -c 'import os, shlex; from dotenv import dotenv_values; values=dotenv_values(os.environ[\"ENV_FILE\"]); [print(\"export \" + key + \"=\" + shlex.quote(value)) for key, value in values.items() if value is not None]')"
[[ "${DEBUG,,}" == false ]] || { echo "DEBUG must be False" >&2; exit 3; }
[[ "${DATABASE_URL:-}" == postgres://* || "${DATABASE_URL:-}" == postgresql://* ]] || {
  echo "Set DATABASE_URL to the VPS PostgreSQL database" >&2; exit 3;
}

mkdir -p "$APP_PATH/backups" "$APP_PATH/shared"
chmod 700 "$APP_PATH/backups"
chgrp richlead "$APP_PATH/shared"
chmod 750 "$APP_PATH/shared"
chgrp richlead "$APP_PATH/shared/.env"
chmod 640 "$APP_PATH/shared/.env"
BACKUP="$APP_PATH/backups/$RELEASE_SHA.dump"
command -v pg_dump >/dev/null 2>&1 || { echo "pg_dump is required for a pre-deploy database backup" >&2; exit 4; }
pg_dump --format=custom --no-owner --no-acl --dbname="$DATABASE_URL" --file="$BACKUP"
chmod 600 "$BACKUP"

.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy

cd "$RELEASE"
npm ci --omit=dev --no-audit --no-fund

ln -s "releases/$RELEASE_SHA" "$APP_PATH/current.next"
mv -Tf "$APP_PATH/current.next" "$CURRENT"
ROLLBACK=1
sudo systemctl restart richlead-api richlead-web

for attempt in {1..20}; do
  HEALTH_HOST=${ALLOWED_HOSTS%%,*}
  if curl --fail --silent --show-error --max-time 5 \
    --header "Host: $HEALTH_HOST" --header 'X-Forwarded-Proto: https' \
    http://127.0.0.1:8000/healthz/ >/dev/null; then
    ROLLBACK=0
    echo "Deployment $RELEASE_SHA is healthy"
    exit 0
  fi
  sleep 2
done
echo "Post-deploy health check failed" >&2
exit 5
