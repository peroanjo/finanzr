from __future__ import annotations

from typing import Any

from apps.api.projection import identifier, number, provider_name
from apps.market_data.fx import CurrencyConversionError, normalize_currency
from apps.market_data.models import Instrument, InstrumentIdentifier
from apps.transactions.models import Transaction


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
        # Transaction identity is internal UUID-backed identity.  Provider IDs
        # belong exclusively to import idempotency and must never cross the
        # public API boundary.
        "id": str(item.id),
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
