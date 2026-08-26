#!/bin/sh
set -eu

project_dir=${FINANZR_PROJECT_DIR:-/opt/finanzr}
cd "$project_dir"

: "${DEMO_PASSWORD:?Define DEMO_PASSWORD con al menos 12 caracteres}"
demo_email=${DEMO_EMAIL:-demo@finanzr.local}

docker compose --env-file .env.production -f compose.production.yaml exec -T backend \
    python manage.py seed_demo_data --email "$demo_email" --password "$DEMO_PASSWORD"

docker compose --env-file .env.production -f compose.production.yaml exec -T backend \
    python manage.py shell -c \
    "from apps.users.models import User; from apps.workspaces.models import Workspace; assert User.objects.count() == 1, f'Usuarios inesperados: {User.objects.count()}'; assert Workspace.objects.count() == 1, f'Workspaces inesperados: {Workspace.objects.count()}'; assert not User.objects.filter(is_superuser=True).exists(); print('Base verificada: exclusivamente Demo')"
