# Architecture overview

Finanzr is a self-hosted application intended for one household or a small
team. The public application uses Vue for the frontend, Django REST Framework
for the API and PostgreSQL for operational data.

## Runtime components

```text
Browser
  │ sessions + CSRF
  ▼
Vue 3 / TypeScript ── REST/JSON ── Django + DRF
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                    PostgreSQL              market-data providers

Python domain and importer packages provide framework-independent financial
rules and import contracts. Docker Compose supplies the local and
production-oriented process boundaries.
```

- `frontend/` contains the Vue shell, views, components, API client, charts and
  i18n catalogs.
- `backend/` contains Django settings, models, migrations, API views,
  authentication, workspace permissions and management commands.
- `finanzr/domain/` contains framework-independent money and portfolio rules.
- `finanzr/importers/` contains deterministic parsers and their public metadata
  contracts.

## Ownership and boundaries

Every financial row is owned by a workspace. Django resolves the active
workspace from the authenticated session and applies role checks at the API
boundary; clients must not select another user's workspace by posting an ID.
The roles are `owner`, `editor` and `viewer`. Market metadata may be shared,
but transactions, balances, imports, audit events and settings remain scoped to
the owning workspace.

Administrative user creation provisions a new, empty personal workspace and an
`owner` membership for that user. It must not grant access to the administrator's
active workspace. The membership model remains the extension point for future
shared workspaces; sharing must be an explicit operation rather than a side
effect of creating an account.

PostgreSQL is the operational store for the Django path. Migrations are the
schema contract. Backups are encrypted by management commands and must be
stored outside the source checkout. Secrets are supplied through environment
or a deployment secret store, never through fixtures or source control.

## Data flow

1. A user authenticates through Django sessions; browser mutations include the
   CSRF token.
2. Vue requests workspace-scoped resources from the REST API.
3. API views authorize the action and delegate financial calculations to domain
   services or model/application services.
4. Imports parse a broker statement into a normalized result, report unsupported
   rows, and persist idempotently using provider operation identifiers.
5. Market data is optional external input. The application stores currency and
   conversion snapshots so historical reporting is reproducible.
6. Vue renders the result and localizes user-facing messages using the selected
   language, with English as the technical fallback.

The workspace export is currently `finanzr-workspace-v2`. This document-level
version records the savings, manual-investment, and manual-portfolio API
cutovers: these resources use UUID identifiers and English fields, including
legacy rows read from the database, while retaining archived history for
complete exports. The remaining fund, stock and crypto sections retain their
existing export shapes until their own reviewed API migrations; there is no
parallel HTTP compatibility route.

## Deployment shape

Development uses `compose.yaml` with PostgreSQL, Django's development server
and Vite. The production-oriented compose file builds a Gunicorn backend and a
static frontend behind the configured ingress. Operators must provide their own
HTTPS, DNS, firewall, secret and backup policy; no public host or operator
identity is encoded in this repository.

## Design records

The workspace boundary, unified account/transaction model and portfolio
projection are recorded in:

- [`adr/0001-workspace-data-boundary.md`](adr/0001-workspace-data-boundary.md)
- [`adr/0002-unified-accounts-and-transactions.md`](adr/0002-unified-accounts-and-transactions.md)
- [`adr/0003-portfolio-as-calculated-projection.md`](adr/0003-portfolio-as-calculated-projection.md)
- [`adr/0004-personal-workspace-provisioning.md`](adr/0004-personal-workspace-provisioning.md)

Changes that alter data ownership, authentication, import semantics, currency
conversion or backup/restore should add or update an ADR and focused tests.
