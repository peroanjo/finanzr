# ADR 0005: Share canonical financial resources through explicit grants

## Status

Accepted

## Context

Users need a private workspace and additional shared workspaces. Copying accounts
into a shared workspace would duplicate imports, movements, balances, and ongoing
maintenance. Granting membership in a private workspace would expose unrelated
financial records.

## Decision

A resource retains its original owning workspace. `AssetShare` grants read or
edit access to one account, manual asset, or real-estate investment in a shared
target workspace. Accounts include all their snapshots and transactions, including
future records. Shared resources cannot be re-shared by recipients. Only a source
workspace owner may create, change, or revoke a grant, and must also be an editor
or owner of the target. Personal workspaces cannot receive grants or invitations.

Effective write access is the intersection of the target membership and resource
grant. A viewer cannot edit even with an edit grant. Read access never implies
access to other source accounts, provider connections, credentials, import batches,
audit logs, or workspace settings. Deleting a canonical resource is possible only
from its owning workspace. Revoking access deletes only the grant.

The existing account, transaction, snapshot, asset, and cash-flow UUIDs remain
canonical. Query boundaries explicitly include granted resources, using subqueries
or distinct rows to avoid duplicate totals. Imports keep the source workspace and
account as their idempotency scope. A recipient cannot move a transaction between
owning workspaces or mutate the source's shared catalog metadata during import.

Both workspaces must use the same reporting currency because stored snapshots and
manual values are already denominated in that currency. Currency changes are
blocked while grants exist. Quotes, splits, and FX conversion for shared holdings
use their original market context. Recipients cannot change foreign workspace-wide
market settings through a resource grant. Combining the same instrument from
multiple owners is supported when their market contexts agree; conflicting manual
quotes, splits, or FX settings fail explicitly rather than producing a mixed value.

Workspace membership roles remain separate from installation administrator roles.
Owners manage membership, rename, and archive shared workspaces. Multiple owners
are allowed, with a workspace row lock preventing removal/demotion of the last
owner. Invitations are email-bound, hashed, expiring, cancellable, and single-use;
acceptance does not overwrite an existing membership role.

The active workspace remains session-scoped. Browser API requests carry the
workspace in which they started; a mismatched session returns 409. Switching
workspaces aborts pending requests, rejects late responses, remounts financial
views/settings, and notifies other tabs to restore their session context.

## Consequences

- Personal and shared views operate on the same records; no synchronization jobs
  or copies are needed.
- Sharing a full account exposes its entire history to target members. The UI
  explains this before granting access.
- Administrators receive no implicit access to another user's financial workspace.
- Independent security review and focused financial/isolation tests cover new
  query boundaries, editing, revocation, and source-context valuation.
- Cross-currency resource sharing and combining incompatible private valuation
  policies require an explicit future design rather than implicit conversions.
