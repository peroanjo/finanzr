# Contributing to Finanzr

Thank you for helping make Finanzr safer and more useful. The project is in
alpha and is built around Vue/Django. Small, reviewable changes are easier to
validate than broad rewrites.

## Before you start

Read the README, [`docs/architecture.md`](docs/architecture.md), the relevant
ADR files and [`SECURITY.md`](SECURITY.md). Do not use real financial exports,
credentials, personal paths, private hosts or private contact details in a
checkout, fixture, screenshot, test, issue or pull request. Use
`seed_demo_data` and the synthetic files under `examples/imports/` instead.

## Local development

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec backend python manage.py migrate
```

The Django tests can be run with `make backend-test`. The framework-independent
financial and importer suites run with `make domain-test`; `make backend-verify`
runs both suites plus the backend configuration, formatting, lint, and type
checks. Frontend checks are run from `frontend/` after dependencies are
installed:

```bash
npm ci
npm test
npm run build
```

If a change needs a different database or external market service, document the
assumption and provide a deterministic test double. Do not make a test depend
on a live provider.

## Language and i18n

English is the source language for Python/TypeScript code, comments, docstrings,
diagnostics and API error identifiers. User-facing text belongs in the i18n
catalogs: Vue messages live under `frontend/src/i18n/` and Django translations
under `backend/locale/`. Add or update the English source and Spanish
translation together, and keep English as the fallback when a key is missing.
Documentation may be written in Spanish or English; keep technical names and
commands unchanged.

Contributors may discuss issues and reviews in Spanish or English. Keep the
canonical code and diagnostic vocabulary in English, and explain any
user-facing Spanish wording in the corresponding catalog change so both
language audiences can review it.

## Scope and design

- Keep workspace ownership and role checks at API boundaries.
- Put financial rules in `finanzr/domain/` so they stay independent of HTTP,
  Django and storage details.
- Keep importers deterministic, idempotent and explicit about unsupported
  formats. Add a clearly synthetic fixture when adding an import contract.
- Preserve EUR reporting and currency snapshots; changes to calculations need
  focused tests and an explanation of rounding or conversion decisions.
- Avoid introducing services, queues or deployment infrastructure without a
  measured need and an architecture note.

## Pull requests

Describe the user-visible result, affected interfaces, migration or data risks,
and the checks you ran. Keep unrelated formatting or generated files out of the
patch. Pull requests should include tests for behavior changes and documentation
for new setup or import formats. Maintainers may ask for a smaller patch when a
change crosses unrelated boundaries.

Use clear imperative commit subjects if you work with commits. Do not rewrite
shared history or add a remote from the repository without explicit project
instructions.

## Security and conduct

Never report a vulnerability in a public issue. Use the private process in
[`SECURITY.md`](SECURITY.md). Participation is governed by
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
