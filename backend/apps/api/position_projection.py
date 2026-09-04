"""Native public projection for calculated traded positions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from apps.api.projection import identifier
from apps.market_data.models import Instrument, InstrumentIdentifier


class PositionProjectionError(RuntimeError):
    """Raised when a calculated position cannot be mapped to its instrument."""


def _position_identity(kind: str) -> tuple[str, str]:
    if kind == Instrument.Kind.CRYPTO:
        return "symbol", InstrumentIdentifier.Scheme.CRYPTO_SYMBOL
    return "isin", InstrumentIdentifier.Scheme.ISIN


def native_position_rows(
    rows: Iterable[Mapping[str, Any]],
    instruments: Iterable[Instrument],
    *,
    kind: str,
    base_currency: str,
) -> list[dict[str, Any]]:
    """Convert private calculation rows to the strict native position DTO.

    The calculators intentionally operate on canonical text identifiers and
    legacy Spanish field names.  This projection is the only boundary where
    those rows become public JSON.  Every calculated row must resolve to a
    visible instrument; silently dropping an orphan would hide financial data.
    """

    identity_key, scheme = _position_identity(kind)
    by_identity: dict[str, Instrument] = {}
    for instrument in instruments:
        if instrument.kind != kind:
            continue
        identity = identifier(instrument, scheme)
        if not identity:
            continue
        existing = by_identity.get(identity)
        if existing is not None and existing.id != instrument.id:
            raise PositionProjectionError(
                f"Multiple {kind} instruments share canonical identity {identity!r}"
            )
        by_identity[identity] = instrument

    result: list[dict[str, Any]] = []
    for row in rows:
        identity = str(row.get(identity_key) or "")
        resolved_instrument = by_identity.get(identity)
        if resolved_instrument is None:
            raise PositionProjectionError(
                f"Calculated {kind} position has no visible instrument for {identity!r}"
            )
        common = {
            "instrument_id": str(resolved_instrument.id),
            "kind": kind,
            "name": resolved_instrument.name,
            "quantity": row.get("participaciones")
            if kind == Instrument.Kind.FUND
            else row.get("titulos"),
            "cost": row.get("total_invertido")
            if kind == Instrument.Kind.FUND
            else row.get("coste_total"),
            "current_price": row.get("precio_actual"),
            "current_value": row.get("valor_actual"),
            "unrealized_pnl": row.get("pnl"),
            "realized_pnl": row.get("pnl_realizada") if kind != Instrument.Kind.FUND else None,
            # Calculation amounts are already in the workspace reporting
            # currency, while this preserves the row's source/quote currency.
            "currency": str(row.get("moneda") or "EUR"),
            "base_currency": base_currency,
        }
        if kind == Instrument.Kind.FUND:
            common.update(
                asset_class=str(row.get("tipo") or ""),
                subtype=str(row.get("subtipo") or ""),
                average_price=row.get("precio_medio"),
                return_percent=row.get("pnl_pct"),
            )
        result.append(common)
    return result
