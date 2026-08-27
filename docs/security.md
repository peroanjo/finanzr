# Finanzr Security

Current security controls and operating requirements.

- `DEBUG` is disabled by default and production requires its own secret key.
- `HttpOnly` and `SameSite=Lax` sessions; in production, `Secure` cookies, HSTS, and HTTPS redirection.
- Django `SessionAuthentication` requires CSRF for every browser mutation.
- Separate rate limits for authentication/uploads and the rest of the API.
- Request bodies and files are limited to 5 MiB; importers validate format and columns.
- CSP, anti-framing, `Referrer-Policy`, and `Permissions-Policy` on every response.
- Mutation auditing without financial bodies, credentials, or plaintext IP addresses.
- Data export and account deletion are available through the API.
- Logical backups are encrypted with Fernet and restoration is protected by explicit confirmation.
- External secrets are encrypted with a master key kept outside PostgreSQL.

## Operations

Generate a key with `Fernet.generate_key()` and store it as
`EXTERNAL_CREDENTIALS_KEY` in the deployment secret manager. Never commit it
or reuse `DJANGO_SECRET_KEY` to encrypt credentials. Keep the same key with the
backup policy: without it, existing backups cannot be decrypted or restored.

```bash
python manage.py backup_database /backups/finanzr-AAAA-MM-DD.json.fernet
python manage.py restore_database /backups/finanzr-AAAA-MM-DD.json.fernet \
  --confirm-empty-database
```

Operational restoration must follow this exact order, with a verified backup
and the application stopped. In a LAN installation, add `-f compose.lan.yaml`
after `-f compose.production.yaml` in every command:

```bash
docker compose --env-file .env.production -f compose.production.yaml stop backend web
docker compose --env-file .env.production -f compose.production.yaml exec -T db sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'
docker compose --env-file .env.production -f compose.production.yaml run --rm backend \
  python manage.py migrate --noinput
docker compose --env-file .env.production -f compose.production.yaml run --rm backend \
  python manage.py restore_database /backups/finanzr-AAAA-MM-DD.json.fernet \
  --confirm-empty-database
docker compose --env-file .env.production -f compose.production.yaml run --rm backend \
  python manage.py check --deploy
docker compose --env-file .env.production -f compose.production.yaml up -d --wait backend web
```

Verify the restoration before publishing the application again; never run it
against a database that already contains data.
