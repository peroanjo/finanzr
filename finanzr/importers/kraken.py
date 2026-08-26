"""Parser for KrakenPro Spot Trades exports."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
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

CRYPTO_NAMES = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "ADA": "Cardano",
    "DOT": "Polkadot",
    "XRP": "XRP",
    "DOGE": "Dogecoin",
    "LTC": "Litecoin",
}
KRAKEN_ASSET_MAP = {"XBT": "BTC", "XDG": "DOGE"}


class KrakenProSpotImporter(BaseImporter):
    # Stable slug: changing it would break deduplication of existing batches.
    slug = "kraken_spot"
    display_name = "KrakenPro Spot Trades"
    target = "crypto_orders"
    target_label = _("Crypto")
    description = _("Imports purchases and sales executed on the KrakenPro spot market.")
    source_instructions = _(
        "In KrakenPro, export the Spot Trades report as CSV. This contract has not "
        "been validated against the classic Kraken product."
    )
    input_kind = InputKind.RECORDS
    formats = (
        ImporterFormat(
            ".csv",
            _("Spot Trades CSV"),
            _("UTF-8 CSV with a header and comma-separated columns."),
        ),
    )
    fields = (
        ImporterField(
            "txid",
            _("Transaction ID"),
            _("Unique identifier used to prevent duplicates."),
            "THVRQM-6JXWD",
        ),
        ImporterField(
            "pair", _("Pair"), _("Traded pair; it must currently be quoted in EUR."), "XBT/EUR"
        ),
        ImporterField(
            "time",
            _("Date and time"),
            _("Time at which the transaction was executed."),
            "2026-06-09 14:32:10",
        ),
        ImporterField("type", _("Type"), _("Transaction direction."), "buy"),
        ImporterField("price", _("Price"), _("Price per crypto unit."), "53440.23"),
        ImporterField("cost", _("Cost"), _("Transaction amount before fees."), "1090.00"),
        ImporterField("fee", _("Fee"), _("Fee charged by KrakenPro."), "2.18"),
        ImporterField("vol", _("Volume"), _("Amount purchased or sold."), "0.020397"),
    )
    rules = (
        _("Only pairs quoted in EUR are imported."),
        _("XBT is normalized to BTC and XDG to DOGE."),
        _("Volume and cost must be positive."),
    )

    def _parse(self, source: list[Mapping[str, Any]], context: ImportContext) -> ImportResult:
        result = ImportResult()
        skipped_pairs: set[str] = set()
        for row_number, row in enumerate(source, start=1):
            pair = str(row["pair"])
            base, _, quote = pair.partition("/")
            base = KRAKEN_ASSET_MAP.get(base.upper(), base.upper())
            if quote.upper() != "EUR":
                skipped_pairs.add(pair)
                result.skipped += 1
                result.issues.append(
                    ImportIssue(
                        code="unsupported_quote_currency",
                        message=gettext("Only pairs quoted in EUR are supported"),
                        row_number=row_number,
                        value=pair,
                    )
                )
                continue
            volume = float(row["vol"] or 0)
            cost = float(row["cost"] or 0)
            fee = float(row["fee"] or 0)
            if volume <= 0 or cost <= 0:
                result.skipped += 1
                result.issues.append(
                    ImportIssue(
                        code="empty_trade",
                        message=gettext("The transaction does not have a positive volume or cost"),
                        row_number=row_number,
                    )
                )
                continue
            operation_type = "Compra" if str(row["type"]).strip().lower() == "buy" else "Venta"
            net_amount = cost + fee if operation_type == "Compra" else cost - fee
            result.records.append(
                {
                    "operacion_id": str(row["txid"]),
                    "fecha_operacion": str(row["time"])[:10],
                    "symbol": base,
                    "nombre_activo": CRYPTO_NAMES.get(base, base),
                    "titulos": volume,
                    "precio_compra": float(row["price"] or 0),
                    "importe_neto": round(net_amount, 2),
                    "comision": fee,
                    "cuenta_id": context.account_id,
                    "tipo_operacion": operation_type,
                }
            )
        result.metadata["skipped_pairs"] = sorted(skipped_pairs)
        return result


IMPORTER = KrakenProSpotImporter()


def parse_kraken_trades(
    records: Iterable[Mapping[str, Any]], account_id: Any
) -> tuple[list[dict[str, Any]], set[str]]:
    """Convenience adapter for callers of the function-based API."""
    result = IMPORTER.parse(records, ImportContext(account_id=account_id))
    return result.records, set(result.metadata["skipped_pairs"])
