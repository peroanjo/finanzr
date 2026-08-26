"""Parser for Trade Republic transaction exports."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from finanzr.domain.money import is_missing

from .base import (
    BaseImporter,
    ImportContext,
    ImporterField,
    ImporterFormat,
    ImportResult,
    InputKind,
)
from .i18n import gettext_noop as _


def _number(value: Any) -> float:
    return 0.0 if is_missing(value) else float(value)


class TradeRepublicImporter(BaseImporter):
    slug = "trade_republic"
    display_name = "Trade Republic Transactions"
    target = "stock_orders"
    target_label = _("Stocks and ETFs")
    description = _("Imports purchases, sales, savings plans, and saveback transactions.")
    source_instructions = _(
        "Export your Trade Republic transaction history as CSV and keep the original header."
    )
    input_kind = InputKind.RECORDS
    formats = (
        ImporterFormat(
            ".csv",
            _("Transaction CSV"),
            _("UTF-8 CSV with a header and comma-separated columns."),
        ),
    )
    fields = (
        ImporterField(
            "transaction_id",
            _("Transaction ID"),
            _("Unique transaction identifier."),
            "7f21c4…",
        ),
        ImporterField("date", _("Date"), _("Execution date."), "2026-05-06"),
        ImporterField(
            "type",
            _("Internal type"),
            _("Record type reported by Trade Republic."),
            "TRADE",
        ),
        ImporterField(
            "category",
            _("Category"),
            _("TRADING or DELIVERY for portfolio transactions."),
            "TRADING",
        ),
        ImporterField("asset_class", _("Asset class"), _("STOCK or ETF."), "ETF"),
        ImporterField("symbol", "ISIN", _("Asset identifier in the export."), "IE00B4L5Y983"),
        ImporterField("name", _("Name"), _("Asset's commercial name."), "iShares Core MSCI World"),
        ImporterField(
            "shares",
            _("Units"),
            _("Quantity; positive for purchases and negative for sales."),
            "10.0694",
        ),
        ImporterField(
            "amount",
            _("Amount"),
            _("Total amount with the original sign from the statement."),
            "-1204.00",
        ),
        ImporterField("fee", _("Fee"), _("Transaction fee."), "1.00"),
        ImporterField("price", _("Price"), _("Price per unit."), "119.57"),
        ImporterField(
            "description",
            _("Description"),
            _("Text used to identify savings plans and saveback."),
            "Savings plan execution",
        ),
        ImporterField(
            "tax",
            _("Taxes"),
            _("Tax withholding associated with saveback, if any."),
            "0.00",
            required=False,
        ),
    )
    rules = (
        _("Only transactions in the TRADING and DELIVERY categories are created."),
        _("STOCK and ETF assets are supported."),
        _("BENEFITS_SAVEBACK records are used to identify cashback purchases."),
    )

    def _parse(self, source: list[Mapping[str, Any]], context: ImportContext) -> ImportResult:
        savebacks = []
        for row in source:
            if row.get("type") == "BENEFITS_SAVEBACK":
                net = abs(_number(row.get("amount"))) - abs(_number(row.get("tax")))
                savebacks.append(round(net, 2))

        orders = []
        for row in source:
            if row.get("category") not in {"TRADING", "DELIVERY"}:
                continue
            if row.get("asset_class") not in {"STOCK", "ETF"} and is_missing(row.get("symbol")):
                continue
            shares = _number(row.get("shares"))
            if shares == 0:
                continue
            amount = _number(row.get("amount"))
            fee = _number(row.get("fee"))
            price = _number(row.get("price"))
            operation_type = "Compra" if shares > 0 else "Venta"
            net_amount = abs(amount)
            if net_amount == 0:
                continue

            is_saveback = False
            description = row.get("description")
            if (
                operation_type == "Compra"
                and not is_missing(description)
                and "Savings plan execution" in str(description)
            ):
                rounded_amount = round(net_amount, 2)
                if rounded_amount in savebacks:
                    is_saveback = True
                    savebacks.remove(rounded_amount)

            orders.append(
                {
                    "operacion_id": str(row["transaction_id"]),
                    "fecha_operacion": str(row["date"])[:10],
                    "isin": str(row["symbol"]),
                    "nombre_activo": str(row["name"]),
                    "titulos": abs(shares),
                    "precio_compra": price,
                    "importe_neto": net_amount,
                    "comision": abs(fee),
                    "cuenta_id": context.account_id,
                    "tipo_operacion": operation_type,
                    "es_saveback": is_saveback,
                }
            )
        support_rows = sum(row.get("type") == "BENEFITS_SAVEBACK" for row in source)
        return ImportResult(
            records=orders,
            skipped=max(0, len(source) - len(orders) - support_rows),
            metadata={"source_rows": len(source), "support_rows": support_rows},
        )


IMPORTER = TradeRepublicImporter()


def parse_trade_republic(
    records: Iterable[Mapping[str, Any]], account_id: Any
) -> list[dict[str, Any]]:
    """Convenience adapter for callers of the function-based API."""
    return IMPORTER.parse(records, ImportContext(account_id=account_id)).records
