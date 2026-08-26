#!/bin/sh
set -eu

project_dir=${FINANZR_PROJECT_DIR:-/opt/finanzr}
cd "$project_dir"

if [ ! -f .env.production ]; then
    echo "Missing $project_dir/.env.production" >&2
    exit 1
fi

mkdir -p backups secrets
chmod 700 backups secrets
chown 10001:10001 backups
chmod 600 .env.production

compose_files="-f compose.production.yaml"
deployment_mode=${FINANZR_LAN:-}
if [ -z "$deployment_mode" ] && [ -f .finanzr-deployment-mode ]; then
    deployment_mode=$(sed -n '1p' .finanzr-deployment-mode)
fi
if [ "$deployment_mode" = "1" ] || [ "$deployment_mode" = "lan" ]; then
    compose_files="$compose_files -f compose.lan.yaml"
    printf '%s\n' lan > .finanzr-deployment-mode
else
    printf '%s\n' production > .finanzr-deployment-mode
fi

owner_password_env=${FINANZR_OWNER_PASSWORD:-}
unset FINANZR_OWNER_PASSWORD
docker compose --env-file .env.production $compose_files build
docker compose --env-file .env.production $compose_files up -d db
docker compose --env-file .env.production $compose_files run --rm backend python manage.py migrate --noinput
docker compose --env-file .env.production $compose_files run --rm backend python manage.py check --deploy
tty_state=
tty_open=0
restore_tty() {
    if [ -n "$tty_state" ]; then
        stty "$tty_state" <&3 2>/dev/null || true
        tty_state=
    fi
    if [ "$tty_open" -eq 1 ]; then
        exec 3<&- || true
        tty_open=0
    fi
}
finish() {
    status=$?
    restore_tty
    trap - 0 HUP INT TERM
    exit "$status"
}
trap finish 0
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

owner_password=
if [ -n "${FINANZR_OWNER_EMAIL:-}" ]; then
    if [ -n "${FINANZR_OWNER_PASSWORD_FILE:-}" ]; then
        password_file=$FINANZR_OWNER_PASSWORD_FILE
        if [ ! -f "$password_file" ]; then
            echo "Password file does not exist: $password_file" >&2
            exit 1
        fi
        file_mode=$(stat -c '%a' "$password_file" 2>/dev/null || stat -f '%Lp' "$password_file" 2>/dev/null || true)
        if [ "$file_mode" != "600" ]; then
            echo "Password file must have mode 600: $password_file" >&2
            exit 1
        fi
        owner_password=$(sed -n '1p' "$password_file")
    elif [ -n "$owner_password_env" ]; then
        echo "Warning: FINANZR_OWNER_PASSWORD is retained for compatibility; use the hidden prompt or FINANZR_OWNER_PASSWORD_FILE instead." >&2
        owner_password=$owner_password_env
    else
        if ! exec 3</dev/tty; then
            echo "FINANZR_OWNER_EMAIL is set, but no interactive terminal is available; set FINANZR_OWNER_PASSWORD_FILE to a mode-600 file." >&2
            exit 1
        fi
        tty_open=1
        if ! tty_state=$(stty -g <&3); then
            echo "Unable to read terminal state for hidden password input." >&2
            exit 1
        fi
        if ! stty -echo <&3; then
            echo "Unable to disable terminal echo for hidden password input." >&2
            exit 1
        fi
        printf 'Owner password (input hidden): ' >&2
        IFS= read -r owner_password <&3 || true
        printf '\n' >&2
        restore_tty
    fi
    owner_password_env=
    if [ -z "$owner_password" ]; then
        echo "The owner password cannot be empty." >&2
        exit 1
    fi
    printf '%s\n' "$owner_password" | docker compose --env-file .env.production $compose_files run -T --rm backend \
        python manage.py bootstrap_owner \
        --email "$FINANZR_OWNER_EMAIL" \
        --password-stdin \
        --workspace "${FINANZR_WORKSPACE_SLUG:-home}" \
        --workspace-name "${FINANZR_WORKSPACE_NAME:-My workspace}"
    owner_password=
else
    owner_password_env=
    echo "Set FINANZR_OWNER_EMAIL to bootstrap the first owner; the installer will ask for the password on /dev/tty."
fi
docker compose --env-file .env.production $compose_files up -d --wait backend web
