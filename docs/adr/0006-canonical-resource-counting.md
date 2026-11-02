# ADR 0006: Count financial resources by canonical identity

## Status

Accepted. Supersedes the read-time name/value exclusion in ADR 0003.

## Context

A legacy heuristic suppressed a manual asset if a real-estate project had a
matching normalized name and live value, with an optional provider comparison.
These attributes are not unique identities. Two independent assets worth EUR
1,000 could be reported as EUR 1,000 instead of EUR 2,000. Sharing resources from
different owners makes these collisions more likely, but private workspaces are
also affected. The heuristic even suppressed manual-only summary sources when
the matching crowdfunding source was not selected.

## Decision

Visible, unarchived manual assets are counted by their canonical model UUIDs.
Real-estate records have their own canonical identities and are counted separately.
No record is suppressed by its name, value, provider, class, or owning workspace.
The existing distinct resource query still prevents multiple sharing links from
counting the same manual record more than once.

This applies consistently to the summary, net-worth history and portfolio
analysis. Selected summary sources continue to control which categories contribute.

## Consequences

- Independent matching records contribute their full values and portfolio weights.
- Sharing still references the original resource, without creating another asset.
- No schema migration or data rewrite is needed; existing records are preserved.
- A genuine historical duplicate must be reconciled explicitly. Matching metadata
  alone cannot safely establish which financial record should be excluded.
- Regression coverage includes private/shared contexts, individual and combined
  summary sources, matching records within one resource type, and repeated grants.
