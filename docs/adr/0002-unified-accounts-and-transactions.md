# ADR 0002 — Unified Accounts and Transactions

- Status: accepted for implementation.
- Date: 2026-07-22.

## Context

The current CSV files separate accounts and orders into savings, manual investment, funds, stocks, and crypto. The funds, stocks, and crypto tables repeat the date, quantity, amount, fee, account, and external identifier. Creating a Django app per provider would perpetuate that duplication and make adding new parsers more expensive.

## Decision

The system will use:

- An `Account` table with a `kind` enum.
- An `AccountSnapshot` table for savings and manual investment.
- A `Transaction` table for funds, stocks, and crypto.
- A global `Instrument` catalogue with multiple identifiers.
- Normalized operation and cash-flow types, while retaining the provider's original type.

Parsers generate normalized DTOs and the application layer converts them into these entities.

## Consequences

- Adding a broker normally does not require new tables.
- Position calculations can be shared across assets.
- Account/instrument compatibility rules are validated in services.
- External identifiers are unique within each account, not globally.
- Specific views continue to exist even though they share persistence.
