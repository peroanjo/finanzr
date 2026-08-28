# ADR 0003 — Portfolio as a Calculated Projection

- Status: accepted for implementation.
- Date: 2026-07-22.

## Context

The legacy model could represent the same asset in both `portfolio_items.csv` and its specialized source. This caused real-estate assets to be duplicated in the summary donut.

## Decision

The portfolio will be a projection of:

- Latest account balances.
- Positions calculated from transactions and prices.
- Live real-estate capital.
- Assets that are exclusively manual.

`ManualAsset` is persisted only when no other source of truth exists. No automatic mirror rows are created in that table.

## Consequences

- An asset is not updated in two places.
- The portfolio total is reproducible from canonical sources.
- Queries are somewhat more complex and require efficient services/selectors.
- At read time, the projection excludes a `ManualAsset` whose normalized name
  and current value match a canonical real-estate project; when both have a
  provider label, those labels must also match.
- This exclusion is non-destructive: the persisted `ManualAsset` row is not
  deleted.
