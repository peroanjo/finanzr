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
- The legacy importer must detect possible duplicates and show them in `dry-run`.
- No ambiguous legacy data is deleted automatically.
