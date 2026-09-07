# Changelog

All notable changes to the public tree will be recorded here. The project is
alpha; entries describe user-visible behavior and release notes rather than
private operational history.

## [Unreleased]

- No changes yet.

## [0.1.0-alpha.1] - 2026-09-08

First public alpha of the self-hosted Finanzr application.

### Added

- Added workspace, role and session-based application foundations.
- Added savings, investment balances, funds, stocks/ETFs, crypto, real-estate
  and portfolio views backed by Django models and APIs.
- Added deterministic domain calculations and importer contracts for fund,
  Trade Republic and KrakenPro statement formats.
- Added synthetic demo generation and public importer fixtures.
- Added public community, security and licensing guidance.
- Added encrypted logical backup and empty-database restoration commands.
- Added reproducible Python dependency locks, pinned container bases and
  release metadata checks.

### Changed

- Established native UUID/English API contracts and aligned the handwritten
  frontend types with the validated OpenAPI schema.
- Centralized currency snapshots, stock-split projections and realized-profit
  calculations in backend/domain code.

### Removed

- Removed the duplicate `/api/crypto-orders/upload-kraken` route. Use
  `/api/crypto-orders/upload-kraken-pro`; the `kraken_spot` importer contract
  and existing import batches remain supported.

### Known limitations

- This release distributes source code built with Docker Compose; versioned
  container images are not published yet.
- Operators must supply HTTPS/ingress, secrets, monitoring and off-host backup
  storage. LAN mode deliberately relaxes secure-cookie and redirect settings.
- Market data is optional external input and may be delayed or unavailable.
- Importers support only the formats and limits listed in the README. Financial,
  tax and investment output must be checked against primary records.
- Schema migrations are forward-oriented. If a migration cannot be reversed,
  recovery requires the previous source revision and a compatible pre-upgrade
  backup.

[Unreleased]: https://github.com/peroanjo/finanzr/compare/v0.1.0-alpha.1...HEAD
[0.1.0-alpha.1]: https://github.com/peroanjo/finanzr/releases/tag/v0.1.0-alpha.1
