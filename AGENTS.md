# Finanzr contributor context

Finanzr is a self-hosted personal-finance dashboard built with Vue 3,
TypeScript, Django REST Framework, and PostgreSQL. Spanish is the product
default and English is the technical fallback. Source code, comments,
docstrings, and diagnostics are written in English; user-facing text belongs in
the English and Spanish i18n catalogues.

## Local development

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: `http://localhost:5173/app/`
- API: `http://localhost:8000/api/`
- Demo data: `docker compose exec backend python manage.py seed_demo_data`

New features should target Vue/Django/PostgreSQL and preserve workspace
isolation, cookie sessions, CSRF protection, and the `owner`, `editor`, and
`viewer` roles.

## Safety and scope

- Never commit real financial exports, operational CSV files, backups, secrets,
  personal paths, hostnames, or deployment addresses.
- Use only obviously synthetic values in tests, fixtures, documentation, and
  screenshots.
- Treat financial calculations, currency conversion, importers, authentication,
  permissions, backups, restoration, and deployment as high-risk changes that
  require focused tests and independent review.
- Do not add Redis, Celery, Kubernetes, or microservices without a measured need.
- Preserve unrelated changes in a shared working tree.

See `CONTRIBUTING.md`, `SECURITY.md`, `docs/architecture.md`, and
`docs/licensing.md` for the public project policies.
