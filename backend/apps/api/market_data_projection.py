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
    # Instrument metadata remains an internal migration/provenance store.  It
    # is deliberately projected only into the two public classification fields
    # and never returned as an opaque JSON blob.
    asset_class = instrument.metadata.get("asset_class", instrument.metadata.get("tipo"))
    subtype = instrument.metadata.get("subtype", instrument.metadata.get("subtipo"))
    return {
        "id": str(instrument.id),
        "kind": instrument.kind,
        "name": instrument.name,
        "quote_currency": instrument.quote_currency or instrument.base_currency or "EUR",
        "identifiers": [
            {
                "scheme": item.scheme,
                "value": item.value,
                "venue": item.venue,
                "is_primary": item.is_primary,
            }
            for item in instrument.identifiers.all()
        ],
        "asset_class": asset_class if isinstance(asset_class, str) and asset_class else None,
        "subtype": subtype if isinstance(subtype, str) and subtype else None,
        "is_active": instrument.is_active,
    }


def instrument_calculation_row(instrument: Instrument) -> dict[str, Any]:
    """Return the private legacy-shaped row consumed by domain calculators."""
    scheme = (
        InstrumentIdentifier.Scheme.CRYPTO_SYMBOL
        if instrument.kind == Instrument.Kind.CRYPTO
        else InstrumentIdentifier.Scheme.ISIN
    )
    row: dict[str, Any] = {
        "isin" if scheme == InstrumentIdentifier.Scheme.ISIN else "symbol": identifier(
            instrument, scheme
        ),
        "ticker": identifier(instrument, InstrumentIdentifier.Scheme.YAHOO),
        "nombre": instrument.name,
        "moneda": instrument.quote_currency or instrument.base_currency or "EUR",
    }
    if instrument.kind == Instrument.Kind.FUND:
        row.update(
            tipo=instrument.metadata.get("asset_class", instrument.metadata.get("tipo", "")),
            subtipo=instrument.metadata.get("subtype", instrument.metadata.get("subtipo", "")),
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
    return {
        "id": str(price.id),
        "instrument_id": str(instrument.id),
        "quoted_at": price.quoted_at.isoformat(),
        "close": number(price.close),
        "currency": price.currency,
        "base_close": number(converted_price),
        "base_currency": base_currency,
        "fx_rate_to_base": number(fx_rate),
        "fx_rate_date": fx_rate_date.isoformat(),
        "fx_source": fx_source,
        "source": price.source,
    }


def price_calculation_row(
    price: MarketPrice | WorkspaceMarketPriceOverride,
    *,
    converted_price: Decimal,
    base_currency: str,
    fx_rate: Decimal,
    fx_rate_date: date,
    fx_source: str,
) -> dict[str, Any]:
    """Return the private legacy-shaped row consumed by position calculators."""
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
