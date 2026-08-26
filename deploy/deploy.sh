#!/bin/sh
set -eu

project_dir=${FINANZR_PROJECT_DIR:-/opt/finanzr}
cd "$project_dir"

if command -v flock >/dev/null 2>&1; then
    exec 9>/run/lock/finanzr-deploy.lock
    flock -n 9 || {
        echo "Another Finanzr deployment is already running" >&2
        exit 1
    }
fi

if [ -z "${FINANZR_COMMIT:-}" ] && command -v git >/dev/null 2>&1 \
    && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    FINANZR_COMMIT=$(git rev-parse --short=7 HEAD)
    if [ -n "$(git status --porcelain)" ]; then
        FINANZR_COMMIT="${FINANZR_COMMIT}-dirty"
    fi
fi
FINANZR_COMMIT=${FINANZR_COMMIT:-unknown}
FINANZR_DEPLOYED_AT=${FINANZR_DEPLOYED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}
FINANZR_VERSION=${FINANZR_VERSION:-$FINANZR_COMMIT}
export FINANZR_COMMIT FINANZR_DEPLOYED_AT FINANZR_VERSION

echo "Deploying $FINANZR_COMMIT ($FINANZR_DEPLOYED_AT)"
./deploy/backup.sh
compose_files="-f compose.production.yaml"
deployment_mode=${FINANZR_LAN:-}
if [ -z "$deployment_mode" ] && [ -f .finanzr-deployment-mode ]; then
    deployment_mode=$(sed -n '1p' .finanzr-deployment-mode)
fi
if [ "$deployment_mode" = "1" ] || [ "$deployment_mode" = "lan" ]; then
    compose_files="$compose_files -f compose.lan.yaml"
fi
docker compose --env-file .env.production $compose_files build
docker compose --env-file .env.production $compose_files run --rm backend \
    python manage.py migrate --noinput
docker compose --env-file .env.production $compose_files run --rm backend \
    python manage.py check --deploy
docker compose --env-file .env.production $compose_files up -d --wait backend web
docker compose --env-file .env.production $compose_files ps
