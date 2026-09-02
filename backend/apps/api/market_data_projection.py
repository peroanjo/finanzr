from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.api.projection import identifier, number
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    MarketPrice,
    WorkspaceMarketPriceOverride,
)


def instrument_row(instrument: Instrument) -> dict[str, Any]:
    scheme = (
        InstrumentIdentifier.Scheme.CRYPTO_SYMBOL
        if instrument.kind == Instrument.Kind.CRYPTO
        else InstrumentIdentifier.Scheme.ISIN
    )
    key = "symbol" if scheme == InstrumentIdentifier.Scheme.CRYPTO_SYMBOL else "isin"
    row = {
        key: identifier(instrument, scheme),
        "ticker": identifier(instrument, InstrumentIdentifier.Scheme.YAHOO),
        "nombre": instrument.name,
        "moneda": instrument.quote_currency or instrument.base_currency or "EUR",
    }
    if instrument.kind == Instrument.Kind.FUND:
        row.update(
            tipo=instrument.metadata.get(
                "asset_class",
                instrument.metadata.get("tipo", ""),
            ),
            subtipo=instrument.metadata.get(
                "subtype",
                instrument.metadata.get("subtipo", ""),
            ),
        )
    return row


def price_row(
    price: MarketPrice | WorkspaceMarketPriceOverride,
    *,
    converted_price: Decimal,
    base_currency: str,
    fx_rate: Decimal,
    fx_rate_date: date,
    fx_source: str,
) -> dict[str, Any]:
    instrument = price.instrument
    is_crypto = instrument.kind == Instrument.Kind.CRYPTO
    scheme = (
        InstrumentIdentifier.Scheme.CRYPTO_SYMBOL if is_crypto else InstrumentIdentifier.Scheme.ISIN
    )
    key = "symbol" if is_crypto else "isin"
    row: dict[str, Any] = {
        key: identifier(instrument, scheme),
        "precio": number(converted_price),
        "updated": price.quoted_at.date().isoformat(),
        "moneda": price.currency,
        "moneda_base": base_currency,
        "precio_orig": number(price.close),
        "tipo_cambio": number(fx_rate),
        "fecha_tipo_cambio": fx_rate_date.isoformat(),
        "fuente_tipo_cambio": fx_source,
    }
    if instrument.kind == Instrument.Kind.STOCK:
        row["fecha"] = price.quoted_at.date().isoformat()
    return row
