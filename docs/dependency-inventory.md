# Resolved dependency inventory for 0.1.0-alpha.1

Generated and reviewed on 2026-09-08 from the committed lockfiles. Registry
metadata is the license/source evidence; package license files remain
authoritative. Python artifacts and hashes are in `backend/requirements/*.lock`;
npm package integrity and registry URLs are in `frontend/package-lock.json`.

## Python runtime

| License | Resolved packages |
| --- | --- |
| Apache-2.0 OR BSD-3-Clause | cryptography@50.0.1 |
| BSD-2-Clause | python-json-logger@4.2.0 |
| BSD-3-Clause/BSD | asgiref@3.12.1, Django@6.1.1, djangorestframework@3.18.1, drf-spectacular@0.28.0, pycparser@3.0, sqlparse@0.6.0, uritemplate@4.2.0 |
| LGPL-3.0-only | psycopg@3.3.5, psycopg-binary@3.3.5 |
| MIT/MIT-0 | attrs@26.1.0, cffi@2.1.1, gunicorn@26.2.0, inflection@0.5.1, jsonschema@4.26.0, jsonschema-specifications@2025.9.1, PyYAML@6.0.3, referencing@0.37.0, rpds-py@2026.6.3 |
| PSF-2.0 | typing-extensions@4.16.0 on Python versions selected by its lock marker |

Python development and audit additions are boolean-py@5.0,
cachecontrol@0.14.4, certifi@2026.7.22, charset-normalizer@3.5.1,
colorama@0.4.6, cyclonedx-python-lib@11.12.0, defusedxml@0.7.1,
django-stubs@5.2.9, django-stubs-ext@6.1.0,
djangorestframework-stubs@3.16.9, filelock@3.32.5, idna@3.19,
iniconfig@2.3.0, librt@0.15.0, license-expression@30.4.4,
markdown-it-py@4.2.0, mdurl@0.1.2, msgpack@1.2.2, mypy@1.19.1,
mypy-extensions@1.1.0, packageurl-python@0.17.6, packaging@26.3,
pathspec@1.1.1, pip@26.2.1, pip-api@0.0.34, pip-audit@2.10.1,
pip-requirements-parser@32.0.1, platformdirs@4.11.7, pluggy@1.6.0,
py-serializable@2.1.0, Pygments@2.21.0, pyparsing@3.3.2,
pytest@9.1.1, pytest-django@4.14.0, requests@2.34.2, rich@15.0.0,
ruff@0.16.6, sortedcontainers@2.4.0, tomli@2.4.1, tomli-w@1.2.0,
types-PyYAML@6.0.12.20260906 and urllib3@2.7.0. Typing-extensions and
tzdata are also present where their platform markers apply. Their metadata
reports permissive MIT/BSD/Apache/PSF/Mozilla families; exact artifacts,
licenses and markers are in `dev.lock`. Source registry:
[PyPI](https://pypi.org/).

## Frontend production graph

The complete production dependency graph reported by npm contains the direct
Vue, Pinia, Vue Router, Vue I18n, Chart.js and Manrope packages plus their
compiler/runtime/build transitives. The following groups cover every resolved
license family; exact names and versions remain machine-readable in the lockfile.

| License | Resolved packages |
| --- | --- |
| OFL-1.1 | @fontsource-variable/manrope@5.3.0 |
| Apache-2.0 | detect-libc@2.1.2, typescript@5.8.3 |
| BSD-2-Clause/BSD-3-Clause/ISC | entities@7.0.1, source-map-js@1.2.1, picocolors@1.1.1 |
| MPL-2.0 | lightningcss@1.33.0 and its platform binding packages |
| MIT | Vue@3.5.40 and its compiler/runtime packages; vue-i18n@11.1.12 and @intlify packages; vue-router@5.3.0; pinia@4.0.3; chart.js@4.5.1; Babel, jridgewell, rolldown, Vite and other remaining production graph packages |

The development graph, including Vitest, Vue Test Utils, ESLint, Prettier,
jsdom and their transitives, is fully enumerated with versions, integrity hashes,
license fields and registry sources in `frontend/package-lock.json`. Source
registry: [npm](https://www.npmjs.com/).

## Container bases

| Image tag | Multi-platform digest |
| --- | --- |
| python:3.14-slim | `sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6` |
| node:24-alpine | `sha256:e67514e5d0f6c46656005e1b693b2ec9d52e80b641307de684d4a015ba7a4eaf` |
| caddy:2.11.4-alpine | `sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648` |
| postgres:17-alpine | `sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73` |
| cloudflare/cloudflared:2026.7.3 | `sha256:e39ee8da81ad5e05d77f38d2f51c60ca51bf2a8450ac3abab50c17fdb91d91bf` |

These digests identify the candidate inputs, but the projects' own license and
notice files inside each image remain authoritative. This alpha distributes
source, not prebuilt images.
