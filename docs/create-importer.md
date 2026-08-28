# How to Add an Importer to Finanzr

Importers convert files from banks, brokers, or exchanges into normalized
records. They all use the same contract and can be tested without web
dependencies, pandas, or disk access.

## Structure

```text
finanzr/importers/
├── base.py              Shared contract and types
├── registry.py          Parser registry
├── funds.py
├── kraken.py
├── trade_republic.py
└── new_provider.py      Your implementation
```

Import the public API from `finanzr.importers`:

```python
from finanzr.importers import (
    BaseImporter,
    ImportContext,
    ImporterField,
    ImporterFormat,
    ImportIssue,
    ImportResult,
    InputKind,
    importers,
)
```

## Common contract

Each implementation inherits from `BaseImporter` and declares:

| Field | Purpose | Example |
|---|---|---|
| `slug` | Stable, unique identifier | `"kraken_spot"` |
| `display_name` | Name shown to users | `"KrakenPro Spot Trades"` |
| `target` | Generated record type | `"crypto_orders"` |
| `target_label` | User-facing target category | `"Crypto"` |
| `description` | Short description shown in the catalogue | `"Imports spot trades."` |
| `source_instructions` | Instructions for obtaining the source file | `"Export Spot Trades as CSV."` |
| `input_kind` | `TEXT` or `RECORDS` | `InputKind.RECORDS` |
| `formats` | Accepted formats and their documentation | `(ImporterFormat(".csv", ...),)` |
| `fields` | Expected fields, examples, and required status | `(ImporterField("txid", ...),)` |
| `rules` | Additional user-facing validation rules | `("One trade per row.",)` |

`accepted_extensions` and `required_fields` are derived read-only properties of
`formats` and `fields`; implementations do not declare them directly.

All parsers receive an `ImportContext` and return an `ImportResult`.

```python
ImportContext(
    account_id=42,
    options={"timezone": "Europe/Madrid"},
)
```

`ImportResult` always contains:

- `records`: valid, already-normalized records.
- `issues`: localized warnings or errors.
- `skipped`: number of skipped rows.
- `metadata`: specific information that is not part of an order.
- `imported`: property containing the number of generated records.

A parser analyzes and normalizes. It must not write to the database, deduplicate
against persisted data, or return HTTP responses.

## Template for a Column-Based CSV

The HTTP adapter may use pandas or `csv.DictReader` to convert a CSV into
records. The parser only receives a sequence of mappings.

```python
from collections.abc import Mapping
from typing import Any

from .base import (
    BaseImporter,
    ImportContext,
    ImporterField,
    ImporterFormat,
    ImportIssue,
    ImportResult,
    InputKind,
)


class NewBrokerImporter(BaseImporter):
    slug = "new_broker"
    display_name = "New Broker"
    target = "stock_orders"
    target_label = "Stocks & ETFs"
    description = "Imports buy and sell orders from New Broker."
    source_instructions = "Export the account activity as CSV."
    input_kind = InputKind.RECORDS
    formats = (
        ImporterFormat(
            ".csv",
            "CSV",
            "Comma-delimited activity export.",
        ),
    )
    fields = tuple(
        ImporterField(name, label, description, example)
        for name, label, description, example in (
            ("operation_id", "Identifier", "Unique operation identifier.", "OP-123"),
            ("date", "Date", "Trade date.", "2026-01-15"),
            ("isin", "ISIN", "Instrument identifier.", "US0000000001"),
            ("quantity", "Quantity", "Number of shares.", "2.5"),
            ("net_amount", "Net amount", "Amount including fees.", "250.00"),
            ("side", "Side", "buy or sell.", "buy"),
        )
    )
    rules = ("One operation per row.",)

    def _parse(
        self,
        source: list[Mapping[str, Any]],
        context: ImportContext,
    ) -> ImportResult:
        result = ImportResult(metadata={"provider": "new_broker"})

        for row_number, row in enumerate(source, start=1):
            try:
                quantity = abs(float(row["quantity"]))
                amount = abs(float(row["net_amount"]))
            except (TypeError, ValueError):
                result.skipped += 1
                result.issues.append(ImportIssue(
                    code="invalid_number",
                    message="Invalid quantity or amount",
                    row_number=row_number,
                ))
                continue

            result.records.append({
                "operacion_id": str(row["operation_id"]),
                "fecha_operacion": str(row["date"])[:10],
                "isin": str(row["isin"]),
                "nombre_activo": str(row.get("name") or row["isin"]),
                "titulos": quantity,
                "precio_compra": float(row.get("price") or 0),
                "importe_neto": amount,
                "comision": abs(float(row.get("fee") or 0)),
                "cuenta_id": context.account_id,
                "tipo_operacion": "Buy" if row["side"] == "buy" else "Sell",
                "es_saveback": False,
            })

        return result


IMPORTER = NewBrokerImporter()
```

## Template for Text, HTML, or Non-Tabular Formats

```python
from .base import BaseImporter, ImportContext, ImportResult, ImporterFormat, InputKind


class NewTextImporter(BaseImporter):
    slug = "new_text"
    display_name = "New text format"
    target = "fund_orders"
    target_label = "Funds"
    description = "Imports fund operations from a text export."
    source_instructions = "Download the operation history as text or HTML."
    input_kind = InputKind.TEXT
    formats = (
        ImporterFormat(".txt", "Text", "Plain-text operation history."),
        ImporterFormat(".html", "HTML", "HTML operation history."),
    )

    def _parse(self, source: str, context: ImportContext) -> ImportResult:
        result = ImportResult()
        for line in source.splitlines():
            # Validate and convert the line.
            pass
        return result
```

## Register the Importer

In `finanzr/importers/__init__.py`:

```python
from .new_provider import IMPORTER as NEW_BROKER_IMPORTER

importers.register(NEW_BROKER_IMPORTER)
```

The registry rejects duplicate slugs. A future interface can discover all
parsers automatically with:

```python
catalog = importers.catalog()
```

To run one:

```python
result = importers.parse(
    "new_broker",
    records,
    ImportContext(account_id=42),
)
```

## Current Normalized Schemas

### `stock_orders`

```text
operacion_id, fecha_operacion, isin, nombre_activo, titulos,
precio_compra, importe_neto, comision, cuenta_id,
tipo_operacion, es_saveback
```

### `crypto_orders`

```text
operacion_id, fecha_operacion, symbol, nombre_activo, titulos,
precio_compra, importe_neto, comision, cuenta_id, tipo_operacion
```

### `fund_orders`

```text
operacion_id, fecha_operacion, fecha_liquidacion, mercado,
tipo_operacion, isin, nombre_fondo, titulos, divisa,
precio_neto, importe_neto, cuenta_id
```

These names form the Django API input contract and must remain stable when they
are converted into typed DTOs.

## Errors and Warnings

A defective row that does not invalidate the rest of the file must produce an
`ImportIssue`:

```python
result.issues.append(ImportIssue(
    code="unsupported_currency",
    message="Only EUR operations are supported",
    severity="warning",
    row_number=7,
    value="USD",
))
result.skipped += 1
```

An input whose complete structure cannot be recognized must raise
`ImporterError`. `BaseImporter` already validates the input type and required
columns for `RECORDS` parsers.

Do not include credentials, complete financial rows, or personal data in error
messages or logs.

## Required Tests

Each new parser must add cases to `tests/test_importers.py` covering at least:

1. A valid file.
2. An invalid or skipped row.
3. Fees and buy/sell signs.
4. An account identifier provided by the context.
5. Specific metadata or warnings.
6. Correct registration in `importers.catalog()`.

Run:

```bash
python3 -m unittest tests.test_importers -v
python3 -m unittest discover -s tests -v
```

## Pull Request Checklist

- The parser inherits from `BaseImporter`.
- It does not import pandas or web-framework dependencies.
- It does not read or write files directly.
- It does not persist or deduplicate against the database.
- It always returns `ImportResult`.
- It uses stable, descriptive issue codes.
- It does not include personal data in fixtures.
- It is registered exactly once.
- It includes tests with entirely fictitious data.
