"""Parser for MyInvestor/Inversis fund statements."""

from __future__ import annotations

import re
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
from .i18n import gettext
from .i18n import gettext_noop as _


def clean_date(value: str) -> str:
    """Extract YYYY-MM-DD and ignore residual broker content."""
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    return match.group(0) if match else value.strip()


def order_from_cells(cells: list[str], account_id: int) -> dict[str, Any] | None:
    """Convert the broker's 11 columns into an order."""
    if len(cells) != 11 or not cells[0] or not cells[0].lstrip()[:1].isdigit():
        return None
    try:
        return {
            "operacion_id": cells[2].strip(),
            "fecha_operacion": clean_date(cells[0]),
            "fecha_liquidacion": clean_date(cells[1]),
            "mercado": cells[3],
            "tipo_operacion": cells[4],
            "isin": cells[5],
            "nombre_fondo": cells[6],
            "titulos": float(cells[7].replace(",", ".")),
            "divisa": cells[8],
            "precio_neto": float(cells[9].replace(",", ".")),
            "importe_neto": float(cells[10].replace(",", ".")),
            "cuenta_id": account_id,
        }
    except (ValueError, IndexError):
        return None


class FundBrokerImporter(BaseImporter):
    slug = "fund_broker"
    display_name = _("MyInvestor/Inversis funds")
    target = "fund_orders"
    target_label = _("Funds")
    description = _("Imports subscriptions, redemptions, and transfers of index funds.")
    source_instructions = _(
        "This file can only be exported by accessing your MyInvestor account through "
        "Inversis. In Inversis, go to Investments → Funds → Operations and Queries → "
        "Operations query → Export Excel."
    )
    input_kind = InputKind.TEXT
    formats = (
        ImporterFormat(
            ".csv",
            _("Semicolon-delimited CSV"),
            _("UTF-8 text without a header; each row must contain 11 columns separated by ;."),
        ),
        ImporterFormat(
            ".html",
            _("HTML table"),
            _("The table exported by the broker; each <tr> row and its 11 cells are processed."),
        ),
        ImporterFormat(
            ".xls",
            _("HTML with an XLS extension"),
            _("Inversis HTML export saved as .xls; it is not a binary Excel workbook."),
        ),
    )
    fields = (
        ImporterField(
            "fecha_operacion",
            _("Trade date"),
            _("Effective date of the order."),
            "2026-01-15",
            position=1,
        ),
        ImporterField(
            "fecha_liquidacion",
            _("Settlement date"),
            _("Date on which the transaction settles."),
            "2026-01-17",
            position=2,
        ),
        ImporterField(
            "operacion_id",
            _("Identifier"),
            _("Unique transaction code."),
            "OP-84721",
            position=3,
        ),
        ImporterField(
            "mercado",
            _("Market"),
            _("Market or channel reported by the broker."),
            "FONDOS",
            position=4,
        ),
        ImporterField(
            "tipo_operacion",
            _("Type"),
            _("Subscription, redemption, or transfer."),
            "SUSCRIPCION",
            position=5,
        ),
        ImporterField(
            "isin", "ISIN", _("International fund identifier."), "IE00B03HCZ61", position=6
        ),
        ImporterField(
            "nombre_fondo",
            _("Fund name"),
            _("Fund's commercial name."),
            "Vanguard Global Stock Index",
            position=7,
        ),
        ImporterField(
            "titulos",
            _("Units"),
            _("Number of units, with a comma or decimal point."),
            "12,458",
            position=8,
        ),
        ImporterField("divisa", _("Currency"), _("Transaction currency code."), "EUR", position=9),
        ImporterField("precio_neto", _("Net price"), _("Price per unit."), "51,4139", position=10),
        ImporterField(
            "importe_neto",
            _("Net amount"),
            _("Total transaction amount."),
            "640,52",
            position=11,
        ),
    )
    rules = (
        _("Rows must keep the exact 11-column order shown."),
        _("Dates must use the YYYY-MM-DD format."),
        _("Subscriptions, redemptions, and inbound or outbound transfers are supported."),
    )

    def _parse(self, source: str, context: ImportContext) -> ImportResult:
        rows: list[list[str]] = []
        source_format = "html" if "<tr" in source.lower() else "csv"
        if source_format == "html":
            html_rows = re.findall(r"<tr>(.*?)</tr>", source, re.DOTALL | re.IGNORECASE)
            for html_row in html_rows:
                cells = re.findall(
                    r"<t[dh][^>]*>(.*?)</t[dh]>", html_row, re.DOTALL | re.IGNORECASE
                )
                cleaned = [
                    re.sub(r"<[^>]+>", "", cell)
                    .strip()
                    .replace("&amp;", "&")
                    .replace("&nbsp;", "")
                    .strip()
                    for cell in cells
                ]
                rows.append([cell for cell in cleaned if cell])
        else:
            rows = [
                [cell.strip().replace("\xa0", "").strip() for cell in line.split(";")]
                for line in source.splitlines()
            ]

        result = ImportResult(metadata={"source_format": source_format})
        for row_number, cells in enumerate(rows, start=1):
            order = order_from_cells(cells, int(context.account_id))
            if order:
                result.records.append(order)
            elif any(cells):
                result.skipped += 1
                result.issues.append(
                    ImportIssue(
                        code="invalid_fund_row",
                        message=gettext(
                            "The row does not contain the expected 11 columns or has invalid values"
                        ),
                        row_number=row_number,
                    )
                )
        return result


IMPORTER = FundBrokerImporter()


def parse_fund_extract(content: str, account_id: int) -> list[dict[str, Any]]:
    """Convenience adapter for callers of the function-based API."""
    return IMPORTER.parse(content, ImportContext(account_id=account_id)).records
