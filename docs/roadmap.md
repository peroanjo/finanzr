# Public roadmap

Finanzr is alpha software. The Vue/Django/PostgreSQL application and its
principal user-facing sections are implemented; current work focuses on
maintainability, contract stability, and a reproducible versioned release.

## Before the first versioned alpha release

- Keep the PostgreSQL-backed frontend and API test suites green.
- Finish explicit OpenAPI coverage for public endpoints and keep frontend types
  aligned with that contract.
- Split oversized frontend views and backend API modules without changing
  financial behavior or workspace boundaries.
- Complete the pre-alpha cleanup of compatibility-shaped API DTOs and IDs.
- Revalidate a clean self-hosted installation and isolated backup restoration
  for the release candidate.
- Resolve the remaining publication-provenance checklist and release checks.

## Later

- Publish versioned releases and release notes.
- Maintain supported-version and vulnerability-reporting policies.
- Maintain measured complexity, duplication, coverage, and bundle budgets.
- Add well-scoped contributor issues for confirmed maintenance or product work.
- Record material architecture decisions as ADRs.

Functional priorities should be represented by public issues. Private portfolio
details and operational deployment notes must never be copied into this roadmap.
