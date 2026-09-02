from __future__ import annotations

from typing import Any

from apps.api.projection import identifier, number, provider_name
from apps.market_data.fx import CurrencyConversionError, normalize_currency
from apps.market_data.models import Instrument, InstrumentIdentifier
from apps.transactions.models import Transaction


def _calculation_operation_label(item: Transaction) -> str:
    """Translate canonical operation types to labels expected by calculations.

    ``provider_operation_type`` is provenance only.  Imported providers may
    use arbitrary labels, so it must never decide whether a row contributes to
    a position or cash-flow calculation.
    """
    if item.instrument.kind == Instrument.Kind.FUND:
        labels: dict[str, str] = {
            Transaction.OperationType.BUY: "SUSCRIPCION",
            Transaction.OperationType.SELL: "REEMBOLSO",
            Transaction.OperationType.TRANSFER_IN: "SUSCR.POR TRASPASO I",
            Transaction.OperationType.TRANSFER_OUT: "REEMB.POR TRASPASO I",
        }
    else:
        labels = {
            Transaction.OperationType.BUY: "Compra",
            Transaction.OperationType.SELL: "Venta",
        }
    return labels.get(item.operation_type, item.operation_type)


def _transaction_calculation_row(item: Transaction) -> dict[str, Any]:
    """Build the legacy-shaped record consumed by pure calculation modules."""
    instrument = item.instrument
    is_crypto = instrument.kind == Instrument.Kind.CRYPTO
    is_fund = instrument.kind == Instrument.Kind.FUND
    scheme = (
        InstrumentIdentifier.Scheme.CRYPTO_SYMBOL if is_crypto else InstrumentIdentifier.Scheme.ISIN
    )
    operation = _calculation_operation_label(item)
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
        "id": str(item.id),
        "fecha_operacion": item.trade_date.isoformat(),
        "titulos": number(item.quantity),
        "importe_neto": number(item.net_amount),
        "cuenta_id": str(item.account_id),
        "cuenta_nombre": item.account.name,
        "plataforma": provider_name(item.account),
        "tipo_operacion": operation,
        "moneda": item.currency,
        "moneda_base": item.base_currency,
        "importe_base": None if base_amount is None else number(base_amount),
        "comision_base": None if base_fee is None else number(base_fee),
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


def transaction_row(item: Transaction) -> dict[str, Any]:
    """Build the strict native-English transaction HTTP representation."""
    internal = _transaction_calculation_row(item)
    instrument = item.instrument
    is_crypto = instrument.kind == Instrument.Kind.CRYPTO
    unit_price_key = "precio_neto" if instrument.kind == Instrument.Kind.FUND else "precio_compra"
    base_unit_price = internal.get("precio_base")
    base_fee = internal.get("comision_base")
    if base_fee is None and item.base_fee is not None:
        base_fee = number(item.base_fee)
    row: dict[str, Any] = {
        "id": str(item.id),
        "account_id": str(item.account_id),
        "account_name": item.account.name,
        "platform": provider_name(item.account),
        "asset_name": (
            internal.get("nombre_fondo") or internal.get("nombre_activo") or instrument.name
        ),
        "trade_date": item.trade_date.isoformat(),
        "settlement_date": (
            item.settlement_date.isoformat() if item.settlement_date is not None else None
        ),
        "operation_type": item.operation_type,
        "cash_flow_type": item.cash_flow_type,
        "quantity": number(item.quantity),
        "unit_price": number(internal[unit_price_key]),
        "net_amount": number(item.net_amount),
        "fee": number(item.fee),
        "currency": item.currency,
        "base_currency": item.base_currency,
        "base_unit_price": base_unit_price,
        "base_net_amount": internal.get("importe_base"),
        "base_fee": base_fee,
        "fx_rate_to_base": internal.get("tipo_cambio"),
        "fx_rate_date": internal.get("fecha_tipo_cambio"),
        "fx_source": internal.get("fuente_tipo_cambio"),
        "market": item.market,
        "provider_operation_type": item.provider_operation_type,
    }
    row["symbol" if is_crypto else "isin"] = internal["symbol" if is_crypto else "isin"]
    if instrument.kind == Instrument.Kind.STOCK:
        row["is_saveback"] = item.is_saveback
    return row
