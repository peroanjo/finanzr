# Release process

This process prepares source-only alpha releases built with Docker Compose. All
validation uses synthetic data and is tied to the exact candidate commit.

## 1. Prepare and review the candidate

1. Update `VERSION`, `CHANGELOG.md`, the supported-version table in
   `SECURITY.md`, and `.github/release-notes/<version>.md`.
2. Regenerate Python locks with `make requirements-lock`. Review dependency
   changes and update `docs/dependency-inventory.md` and required notices.
3. Refresh base-image digests deliberately and record them in the dependency
   inventory. A tag plus digest is used so updates remain visible and immutable.
4. Run `make release-check`, backend verification and every frontend check.
5. Open a pull request. Changes to calculations, conversion, importers,
   authentication, permissions, backups, restoration or deployment require an
   independent reviewer familiar with that area.
6. Wait for every required CI and Security check on the final commit. Require
   the branch to be up to date before merge.

Open dependency-update pull requests are not implicitly part of a candidate.
Include only updates whose own checks pass and whose change is reviewed; record
any intentional deferral in the release notes.

## 2. Validate operations

Using only the published README and `docs/security.md`, validate the exact
candidate from a clean checkout or source archive in an isolated environment:

- install, migrate, create the first owner and empty workspace;
- sign in and out; exercise owner, editor and viewer authorization and workspace
  isolation;
- create/update/delete representative savings and investment records and import
  each synthetic fixture under `examples/imports/`;
- create an encrypted backup, restore it to a separate empty database, and
  compare representative counts and values;
- update from the previous supported tag, recording source and image identifiers
  before and after; exercise recovery with the previous code and compatible
  pre-upgrade backup, noting any irreversible migration.

Record the UTC time, candidate SHA, OS/architecture, Docker and Compose versions,
commands, pass/fail result, reviewer and limitations in the pull request or a
private release record. Never record secrets, filesystem paths, hostnames,
addresses or real financial data. The automated tests support this exercise but
do not replace the operational backup/restore and update rehearsal.

## 3. Tag and draft

After the reviewed pull request is merged, use the merge commit as the candidate:

```bash
git switch main
git pull --ff-only
python3 scripts/check_release.py --tag v0.1.0-alpha.1
git tag -a v0.1.0-alpha.1 -m 'Finanzr v0.1.0-alpha.1'
git push origin v0.1.0-alpha.1
```

The tag workflow repeats the metadata check and creates a draft GitHub
pre-release from the matching notes file. Confirm that the tag SHA is the
reviewed commit and that CI and Security succeeded for it. Review installation,
update, recovery and limitation links in the draft, then publish it manually as
a pre-release.

Finally download both automatically generated source archives, verify they are
for the same tag, and repeat `scripts/check_release.py --tag <tag>` from one
archive. The GitHub Releases badge in the README includes pre-releases.
