# Licensing, assets and project marks

## Project license

The Finanzr source tree is distributed under the GNU Affero General Public
License, version 3. The complete, unmodified license text is in
[`LICENSE`](../LICENSE). The AGPL's source and network-use obligations apply to
covered modifications; consult the license text for the exact terms.

This file does not name a copyright holder or grant rights on behalf of anyone
not identified in the applicable work. Contributors must not add another
person's copyright or contact details without permission.

## Dependency inventory

The resolved runtime and development inventory, including transitive packages,
licenses and registry sources, is recorded in
[`dependency-inventory.md`](dependency-inventory.md). Python artifacts are
fixed by hash in `backend/requirements/*.lock`; frontend artifacts and integrity
hashes are fixed by `frontend/package-lock.json`. The direct version ranges
remain in `backend/requirements/*.txt` and `frontend/package.json` so updates can
be reviewed deliberately.

| Area | Direct packages | Declared/upstream license family | Version source |
| --- | --- | --- | --- |
| Backend | Django, Django REST Framework, drf-spectacular | BSD-family | `backend/requirements/base.txt` and `base.lock` |
| Backend | psycopg | LGPL-3.0-only | `backend/requirements/base.txt` and `base.lock` |
| Backend | gunicorn, python-json-logger | MIT/BSD-family | `backend/requirements/base.txt` and `base.lock` |
| Backend | cryptography | Apache-2.0 OR BSD-3-Clause | `backend/requirements/base.txt` and `base.lock` |
| Python development | pytest, pytest-django, ruff, mypy, django-stubs | MIT/BSD-family | `backend/requirements/dev.txt` and `dev.lock` |
| Frontend | Vue, Pinia, Vue Router, Vue I18n, Chart.js | MIT | `frontend/package.json` and `package-lock.json` |
| Frontend toolchain | TypeScript, Vite, Vitest, Vue Test Utils, jsdom | MIT/Apache-family | `frontend/package.json` and `package-lock.json` |
| Font | `@fontsource-variable/manrope` | OFL-1.1 | `frontend/public/THIRD_PARTY_NOTICES.txt` |

The npm lockfile records package versions, integrity values and many package
license fields. A release build must still run a license inventory over the
resolved tree because transitive packages can change when ranges are updated.
Python dependency ranges are intentionally not a license lock; inspect the
installed wheels or sdist metadata during release preparation.

## Bundled and externally loaded assets

- The frontend uses a text-based mark and CSS styling created in this project;
  no unprovenanced raster logo is distributed.
- The files in `docs/assets/screenshots/` are application captures from an
  isolated Spanish-language workspace created with `seed_demo_data` on
  2026-09-07. Every displayed identity, holding and value is synthetic. The
  README presents the separate vector mark in `docs/assets/finanzr-header.svg`
  as its header; no screenshot is used as a header image.
- The current frontend bundles its npm dependencies and Manrope font files. It
  does not load JavaScript, CSS or fonts from public CDNs. The Manrope copyright
  and complete OFL-1.1 terms are copied into the built web artifact as
  `THIRD_PARTY_NOTICES.txt`.
- No real account exports, screenshots, photographs or customer data are
  intended to be distributed. Demo records and importer fixtures are synthetic.

## Trademark, logo and screenshot policy

The names “Finanzr” and “Finanzr” logo are project marks. AGPL permission to
copy or modify the code does not grant trademark rights. You may truthfully say
that a build is based on Finanzr, but do not imply that a modified build is an
official release, endorsement or hosted service. Do not register confusingly
similar names or domains.

Screenshots and videos must use `seed_demo_data` or other obviously synthetic
records. Remove emails, account names, balances, transaction identifiers,
broker exports, private URLs and browser notifications before publication. A
modified screenshot should be labelled as such and must not use a real person's
portfolio as a marketing example.

Questions about asset provenance or proposed branding changes belong in a
private maintainer discussion; do not publish personal contact information in
this document.
