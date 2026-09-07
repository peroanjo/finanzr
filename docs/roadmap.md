# Public roadmap

Finanzr is alpha software. The Vue/Django/PostgreSQL application and its
principal user-facing sections are implemented; current work focuses on
maintainability, contract stability, and a reproducible versioned release.

## First alpha release status

- PostgreSQL backend, domain, frontend, OpenAPI, type, lint, security and image
  checks are implemented in CI and are required on `main`.
- Public endpoints have explicit OpenAPI coverage. Frontend DTOs use the native
  UUID/English contract and are checked by TypeScript and contract tests.
- The backend API monolith and the principal Funds, Stocks, Crypto and Settings
  view responsibilities have been split. Remaining large views are maintenance
  improvements, not known release blockers.
- Compatibility HTTP routes and public legacy-shaped IDs targeted by the
  pre-alpha cleanup are removed. Private projections remain intentionally at
  the boundary of established calculation/import formats.
- Reproducible dependency locks, digest-pinned base images, centralized version
  metadata and release checks are in place.
- The exact release candidate still requires the operational validation,
  independent review and green GitHub checks described in
  [`release-process.md`](release-process.md).

## Later

- Publish versioned container images if demand justifies an image registry.
- Maintain supported-version and vulnerability-reporting policies.
- Maintain measured complexity, duplication, coverage, and bundle budgets.
- Add well-scoped contributor issues for confirmed maintenance or product work.
- Record material architecture decisions as ADRs.

Functional priorities should be represented by public issues. Private portfolio
details and operational deployment notes must never be copied into this roadmap.
