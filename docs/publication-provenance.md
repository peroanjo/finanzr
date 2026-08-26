# Public-tree provenance

This public candidate was prepared from private source commit
`5c56e6876bcea212e4a54807a115382da0395827` on 2026-08-25.

The private Git history was deliberately discarded. The export excluded all
operational `data/` files, database backups, spreadsheets, broker exports,
secrets, local settings, caches, and build outputs. Historical migration notes
and deployment helpers containing machine-specific details were also removed.

The files in `examples/imports/` were created from the documented parser
contracts and contain synthetic values only. Demo application data is generated
by `python manage.py seed_demo_data`.

## Publication gates

- [x] Source commit recorded.
- [x] Private Git history excluded.
- [x] Operational datasets and exports excluded.
- [x] Local configuration and machine-specific deployment files excluded.
- [x] Synthetic importer examples documented.
- [x] Independent secret scanners completed on the final new Git history
      (Gitleaks and TruffleHog, 2026-08-25).
- [x] Clean installation and isolated backup restoration verified locally.
- [ ] Private GitHub staging repository audited.
- [ ] Repository visibility explicitly approved by the owner.

The original private repository and its data remain separate and must never be
connected to the public remote.
