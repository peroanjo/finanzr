# Support

Finanzr is community-maintained alpha software for self-hosted installations.
Support is provided on a best-effort basis through the issue or discussion
facilities enabled by the repository host. If those facilities are disabled in
your mirror, consult the documentation and your local maintainers rather than
assuming that an upstream response channel exists.

## Good questions and bug reports

Before asking for help, check the README, the relevant document under `docs/`,
existing issues and the output of `docker compose config`. Include:

- the Finanzr source version or commit;
- operating system, Docker/Compose and browser versions;
- the command that failed and a redacted error/log excerpt;
- whether the issue reproduces with a fresh synthetic demo workspace.

Never attach real bank, broker or exchange exports, database backups, secrets,
passwords, tokens, personal paths, private domains or unredacted screenshots.
Replace them with the fixtures in `examples/imports/` or a minimal synthetic
example.

## What this project does not provide

Maintainers do not provide financial, tax, legal, investment or accounting
advice; managed hosting; guaranteed uptime; custom integrations; or recovery of
data that was not backed up by the operator. Provider formats and external
market data can change without notice. Verify every import and calculation
against the original statement.

## Security

Do not use public issues or discussions for vulnerabilities. Follow the private
reporting process in [`SECURITY.md`](SECURITY.md).
