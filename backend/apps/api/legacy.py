from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet

from apps.accounts.models import Account
from apps.market_data.fx import CurrencyConversionError, normalize_currency
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    MarketPrice,
    WorkspaceMarketPriceOverride,
)
from apps.transactions.models import Transaction
from finanzr.importers import importers


def number(value: Any) -> float:
    return float(value or 0)


def next_legacy_id(objects: QuerySet[Any]) -> int:
    return max((obj.legacy_id or 0 for obj in objects), default=0) + 1


def provider_name(obj: Any) -> str:
    return str(obj.provider.name if obj.provider_id else obj.provider_label)


def identifier(instrument: Instrument, scheme: str) -> str:
    result = next((item for item in instrument.identifiers.all() if item.scheme == scheme), None)
    return result.value if result else ""


def account_row(account: Account) -> dict[str, Any]:
    """Return the native public projection for a traded account.

    ``external_id`` remains storage for imported legacy data, but it is not a
    public identity.  Account primary keys are UUIDs for every traded API
    consumer, including rows created from an older installation.
    """

    importer_name = ""
    if account.importer_slug:
        try:
            importer_name = importers.get(account.importer_slug).display_name
        except KeyError:
            importer_name = account.importer_slug
    row = {
        "id": str(account.id),
        "name": account.name,
        "platform": provider_name(account),
        "type": account.subtype,
        "currency": account.currency,
        "importer_slug": account.importer_slug,
        "importer_name": importer_name,
    }
    return row


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


def transaction_row(item: Transaction) -> dict[str, Any]:
    instrument = item.instrument
    is_crypto = instrument.kind == Instrument.Kind.CRYPTO
    is_fund = instrument.kind == Instrument.Kind.FUND
    scheme = (
        InstrumentIdentifier.Scheme.CRYPTO_SYMBOL if is_crypto else InstrumentIdentifier.Scheme.ISIN
    )
    operation_labels: dict[str, str] = {
        Transaction.OperationType.BUY: "Compra",
        Transaction.OperationType.SELL: "Venta",
        Transaction.OperationType.TRANSFER_IN: "SUSCR.POR TRASPASO I",
        Transaction.OperationType.TRANSFER_OUT: "REEMB.POR TRASPASO I",
    }
    operation = item.provider_operation_type or operation_labels.get(
        item.operation_type, item.operation_type
    )
    try:
        quote_currency = normalize_currency(item.currency)
        base_currency = normalize_currency(item.base_currency or item.currency)
    except CurrencyConversionError:
        quote_currency = ""
        base_currency = ""
    same_currency = bool(quote_currency and quote_currency == base_currency)
    base_amount = item.base_net_amount
    if base_amount is None and same_currency:
        base_amount = item.net_amount
    base_unit_price = item.base_unit_price
    if base_unit_price is None and same_currency:
        base_unit_price = item.unit_price
    base_fee = item.base_fee
    if base_fee is None and same_currency:
        base_fee = item.fee
    row: dict[str, Any] = {
        "operacion_id": item.external_id or str(item.id),
        "fecha_operacion": item.trade_date.isoformat(),
        "titulos": number(item.quantity),
        "importe_neto": number(item.net_amount),
        # The transaction envelope intentionally keeps its transitional
        # Spanish key; only the value changes to the account UUID.
        "cuenta_id": str(item.account_id),
        "cuenta_nombre": item.account.name,
        "plataforma": provider_name(item.account),
        "tipo_operacion": operation,
        "moneda": item.currency,
        "moneda_base": item.base_currency,
        "importe_base": None if base_amount is None else number(base_amount),
        "tipo_cambio": (
            number(item.fx_rate_to_base)
            if item.fx_rate_to_base is not None
            else (1.0 if same_currency else None)
        ),
        "fecha_tipo_cambio": (
            item.fx_rate_date.isoformat() if item.fx_rate_date else item.trade_date.isoformat()
        ),
        "fuente_tipo_cambio": item.fx_source or ("identity" if same_currency else ""),
    }
    if is_fund:
        row.update(
            fecha_liquidacion=item.settlement_date.isoformat() if item.settlement_date else "",
            mercado=item.market,
            isin=identifier(instrument, scheme),
            nombre_fondo=item.raw_metadata.get("legacy_name", instrument.name),
            divisa=item.currency,
            precio_neto=number(item.unit_price),
            precio_base=None if base_unit_price is None else number(base_unit_price),
        )
    else:
        row.update(
            **{("symbol" if is_crypto else "isin"): identifier(instrument, scheme)},
            nombre_activo=item.raw_metadata.get("legacy_name", instrument.name),
            precio_compra=number(item.unit_price),
            precio_base=None if base_unit_price is None else number(base_unit_price),
            comision=number(item.fee),
            comision_base=None if base_fee is None else number(base_fee),
        )
        if not is_crypto:
            row["es_saveback"] = item.is_saveback
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
