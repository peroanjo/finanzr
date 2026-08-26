# Required `main` branch settings

Configure these settings in the GitHub repository before accepting external
pull requests. They are intentionally documented here rather than applied by
automation, because branch protection is an owner decision and requires GitHub
repository administration.

Enable pull requests and require the branch to be up to date before merging.
Require at least one approval for ordinary changes; require an additional
review from the relevant maintainer when a change affects financial
calculations, currency conversion, imports, authentication, permissions,
backups, restoration, or deployment.

Require these status checks after the first successful run has established
their exact GitHub check names:

- `Backend tests`
- `Domain compatibility tests`
- `Backend quality`
- `Frontend`
- `Production container builds`
- `Python dependency audit`
- `npm dependency audit`
- `Secret scan`
- `CodeQL (python)`
- `CodeQL (javascript-typescript)`

Also require resolved review conversations, disable force-pushes and branch
deletion, and keep the default branch restricted to reviewed pull requests.
Enable GitHub secret scanning, push protection, and Dependabot alerts when the
repository is created. Do not add `CODEOWNERS` until maintainers and ownership
areas are explicitly assigned.
