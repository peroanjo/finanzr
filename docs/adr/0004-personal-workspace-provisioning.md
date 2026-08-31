# ADR 0004: Provision a private workspace for every administrative user creation

## Status

Accepted

## Context

The administration API historically created a user by adding an `editor`
membership to the administrator's active workspace. A newly created account
therefore saw the administrator's balances immediately. Users created through
Django Admin could instead have no membership and fail when the API resolved an
active workspace.

## Decision

Every user created through either administrative interface receives a new empty
workspace and an `owner` membership. The workspace has a deterministic internal
slug derived from the user's UUID. Account roles (`admin`, `user`, and `demo`)
remain installation-wide and separate from workspace roles (`owner`, `editor`,
and `viewer`).

Existing membership and invitation models remain in place so explicit shared
workspace support can be built later. Creating an account never implies sharing
the creator's workspace.

## Consequences

- New accounts cannot read financial data from the administrator's workspace.
- Workspace sharing remains representable without coupling it to account
  provisioning.
- A data migration repairs accounts created under the old behavior and users
  that currently have no workspace.
