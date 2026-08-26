# Security policy

Finanzr handles personal financial records, so security reports are welcome.
Please do not publish credentials, private exports, exploit details or
personally identifying information in a public issue, pull request or
discussion.

## Supported versions

The current `main` line is the only supported alpha line until the project
publishes a versioned release. Older snapshots may contain known issues and
should not be exposed to an untrusted network.

## Report a vulnerability privately

Use the repository host's **Security** tab and choose **Advisories → Report a
vulnerability** to create a private security advisory. This is the preferred
channel and does not require publishing a personal email address. If private
advisories are unavailable in a particular mirror, ask that mirror's
maintainers for its private security channel; do not use a public issue.

Include, when safe:

- a short description and affected component or version;
- reproduction steps or a minimal proof of concept with synthetic data;
- the security impact and any required privileges or configuration;
- a suggested mitigation, if known.

Do not attach real account exports, keys, passwords, tokens, private URLs or
unredacted logs. If you accidentally disclose a secret, revoke it immediately
and mention only the rotation status in the report.

## Response and disclosure

Maintainers will acknowledge a private report through the advisory channel,
triage its impact, and coordinate a fix or mitigation before public disclosure
when practical. Timelines depend on severity, reproducibility and maintainer
availability. Credit is optional and will only be given with the reporter's
permission.

Security fixes may require a migration, backup or configuration change. Release
notes will describe user action without exposing exploit details. After a fix is
available, the advisory can be published by the maintainers when doing so no
longer increases user risk.

## Scope

In scope are the Finanzr source tree, its authentication and workspace
isolation, import validation, backup/restore commands, Docker configuration and
the published build instructions. Vulnerabilities in third-party providers,
Docker, PostgreSQL, browsers or operating systems should be reported to their
respective maintainers, while a concise impact note may still help Finanzr
coordinate a mitigation.

For conduct concerns, use the private process described in
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
