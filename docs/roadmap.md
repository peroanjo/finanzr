# Public roadmap

Finanzr is currently an alpha while the Vue/Django implementation continues to
expand its coverage and production readiness.

## Before the first public release

- Keep the PostgreSQL-backed frontend and API test suites green.
- Complete explicit OpenAPI schemas for public API endpoints.
- Add reproducible lint, type-check, dependency-audit, and container-build CI.
- Validate a clean self-hosted installation and an isolated backup restoration.
- Complete the remaining user-facing views and release checks.
- Audit the private GitHub staging repository before changing its visibility.

## Later

- Publish versioned releases and release notes.
- Maintain supported-version and vulnerability-reporting policies.
- Add well-scoped contributor issues after the installation path is proven.
- Record material architecture decisions as ADRs.

Functional priorities should be represented by public issues once the staging
repository exists. Private portfolio details and operational deployment notes
must never be copied into this roadmap.
