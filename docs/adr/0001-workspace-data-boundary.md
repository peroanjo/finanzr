# ADR 0001 — Workspace as the Data Boundary

- Status: accepted for implementation.
- Date: 2026-07-22.

## Context

Finanzr will move from a single-user installation to supporting users, permissions, and potentially shared finances. Associating every row directly with a user would prevent sharing a financial set without duplicating or redesigning it.

## Decision

`Workspace` is the ownership unit. Users access it through `WorkspaceMembership` with `owner`, `editor`, or `viewer` roles.

Private root objects have `workspace_id`. Child objects such as snapshots and transactions inherit ownership through their account, avoiding duplicate foreign keys that could become inconsistent.

The authorized workspace is derived from the session and memberships. A client-supplied `user_id` or `workspace_id` never grants access by itself.

## Consequences

- Personal and shared finances use the same model.
- Every private query requires an explicit scope.
- Systematic horizontal-access tests are required.
- The last owner cannot leave a workspace without transferring ownership or purging it.
- Future export and deletion operations run per workspace.
