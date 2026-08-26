## Summary

<!-- Describe the user-visible result and the affected area. -->

## Risk and migration notes

- [ ] No financial calculation, currency conversion, importer, authentication,
      permissions, backup, restoration, or deployment behavior changed.
- [ ] If a high-risk area changed, focused tests and the relevant migration or
      rollback notes are included.
- [ ] No real exports, credentials, private URLs, or personal data are included.

## Verification

<!-- List the exact commands or CI jobs run, and explain any known blocker. -->

- [ ] Backend checks and tests
- [ ] Domain compatibility tests (when relevant)
- [ ] Frontend checks and build (when relevant)
- [ ] Security checks (when relevant)

## Review checklist

- [ ] The change is scoped and unrelated local work is preserved.
- [ ] Documentation and i18n catalogues are updated when needed.
- [ ] Tests use synthetic, deterministic data.
