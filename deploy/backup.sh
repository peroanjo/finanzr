#!/bin/sh
set -eu

project_dir=${FINANZR_PROJECT_DIR:-/opt/finanzr}
cd "$project_dir"

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
destination="/backups/finanzr-$timestamp.json.fernet"

compose_files="-f compose.production.yaml"
deployment_mode=${FINANZR_LAN:-}
if [ -z "$deployment_mode" ] && [ -f .finanzr-deployment-mode ]; then
    deployment_mode=$(sed -n '1p' .finanzr-deployment-mode)
fi
if [ "$deployment_mode" = "1" ] || [ "$deployment_mode" = "lan" ]; then
    compose_files="$compose_files -f compose.lan.yaml"
fi
docker compose --env-file .env.production $compose_files exec -T backend \
    python manage.py backup_database "$destination"

find backups -type f -name 'finanzr-*.json.fernet' -mtime +14 -delete
