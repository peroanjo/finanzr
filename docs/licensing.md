# Licensing, assets and project marks

## Project license

The Finanzr source tree is distributed under the GNU Affero General Public
License, version 3. The complete, unmodified license text is in
[`LICENSE`](../LICENSE). The AGPL's source and network-use obligations apply to
covered modifications; consult the license text for the exact terms.

This file does not name a copyright holder or grant rights on behalf of anyone
not identified in the applicable work. Contributors must not add another
person's copyright or contact details without permission.

## Direct dependency inventory

The following is an initial inventory based on the manifests committed in this
tree. It is not a substitute for checking the exact installed distribution and
its transitive notices before redistributing an image.

| Area | Direct packages | Declared/upstream license family | Evidence and follow-up |
| --- | --- | --- | --- |
| Backend | Django, Django REST Framework, drf-spectacular | BSD-family | Verify exact notices from the installed distributions. |
| Backend | psycopg | LGPL family | Preserve its license notices when redistributing binaries. |
| Backend | gunicorn, python-json-logger | MIT/BSD-family | Verify installed metadata. |
| Backend | cryptography | Apache-2.0/BSD-family | Verify the selected version and bundled backend notices. |
| Python development | pytest, pytest-django, ruff, mypy, django-stubs | MIT/BSD-family | Development-only dependencies may still appear in build environments. |
| Frontend | Vue, Pinia, Vue Router, Vue I18n, Chart.js | MIT | Check the npm lockfile and retain package notices. |
| Frontend | TypeScript, Vite, Vitest, Vue Test Utils, jsdom, Node types | MIT-family | Development-only dependencies; audit the complete npm tree. |
| Frontend | `@fontsource-variable/manrope` | SIL Open Font License family | Keep the font's upstream OFL notice with redistributed assets. |

The npm lockfile records package versions, integrity values and many package
license fields. A release build must still run a license inventory over the
resolved tree because transitive packages can change when ranges are updated.
Python dependency ranges are intentionally not a license lock; inspect the
installed wheels or sdist metadata during release preparation.

## Bundled and externally loaded assets

- The frontend uses a text-based mark and CSS styling created in this project;
  no unprovenanced raster logo is distributed.
- The files in `docs/assets/screenshots/` are real application captures from an
  isolated English-language workspace created with `seed_demo_data` on
  2026-08-26. Every displayed identity, holding and value is synthetic.
- `docs/assets/finanzr-hero.webp` was composed specifically for this repository
  from those five captures with OpenAI's image-generation tooling on
  2026-08-26. It contains no operational data. To the extent that copyright
  applies to the generated output, it is distributed as project artwork under
  the repository license.
- The bundled HTML entry point references Chart.js, chartjs-chart-financial and
  Google Fonts from public CDNs. These are external runtime dependencies, not a
  grant to mirror or redistribute them. Verify their upstream licenses,
  availability and integrity before using the entry point in a release.
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
