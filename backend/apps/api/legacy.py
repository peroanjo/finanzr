from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import QuerySet

from apps.accounts.models import Account
from apps.common.models import InstallationSettings
from apps.market_data.fx import CurrencyConversionError, normalize_currency
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    MarketPrice,
    WorkspaceMarketPriceOverride,
)
from apps.real_estate.models import RealEstateCashFlow, RealEstateInvestment
from apps.real_estate.withholding import effective_withholding_rate, net_profit
from apps.transactions.models import Transaction
from finanzr.importers import importers


def number(value: Any) -> float:
    return float(value or 0)


def account_id(account: Account) -> int:
    if account.external_id and account.external_id.rsplit(":", 1)[-1].isdigit():
        return int(account.external_id.rsplit(":", 1)[-1])
    raise ValueError(f"Account {account.id} has no legacy identifier")


def next_account_id(accounts: QuerySet[Account]) -> int:
    values = [account_id(account) for account in accounts if account.external_id]
    return max(values, default=0) + 1


def next_legacy_id(objects: QuerySet[Any]) -> int:
    return max((obj.legacy_id or 0 for obj in objects), default=0) + 1


def provider_name(obj: Any) -> str:
    return str(obj.provider.name if obj.provider_id else obj.provider_label)


def identifier(instrument: Instrument, scheme: str) -> str:
    result = next((item for item in instrument.identifiers.all() if item.scheme == scheme), None)
    return result.value if result else ""


def account_row(account: Account, provider_field: str = "plataforma") -> dict[str, Any]:
    importer_name = ""
    if account.importer_slug:
        try:
            importer_name = importers.get(account.importer_slug).display_name
        except KeyError:
            importer_name = account.importer_slug
    row = {
        "id": account_id(account),
        "nombre": account.name,
        "tipo": account.subtype,
        "moneda": account.currency,
        "importer_slug": account.importer_slug,
        "importer_name": importer_name,
        provider_field: provider_name(account),
    }
    if account.kind == Account.Kind.CRYPTO:
        row.pop("tipo")
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
        "cuenta_id": account_id(item.account),
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


def real_estate_amount(item: RealEstateInvestment, flow_type: str) -> Decimal:
    return sum(
        (flow.amount for flow in item.cash_flows.all() if flow.flow_type == flow_type),
        Decimal("0"),
    )


def real_estate_row(
    item: RealEstateInvestment,
    *,
    default_tax_rate: Decimal | None = None,
) -> dict[str, Any]:
    contribution = real_estate_amount(item, RealEstateCashFlow.FlowType.CONTRIBUTION)
    reinvestment = real_estate_amount(item, RealEstateCashFlow.FlowType.REINVESTMENT)
    returned = real_estate_amount(item, RealEstateCashFlow.FlowType.CAPITAL_RETURN)
    profit = real_estate_amount(item, RealEstateCashFlow.FlowType.PROFIT)
    effective_rate = effective_withholding_rate(
        item,
        default_tax_rate
        if default_tax_rate is not None
        else InstallationSettings.load().default_crowdfunding_tax_rate,
    )
    dated_flows = sorted(
        (
            flow
            for flow in item.cash_flows.all()
            if flow.flow_type
            in {
                RealEstateCashFlow.FlowType.CAPITAL_RETURN,
                RealEstateCashFlow.FlowType.PROFIT,
            }
        ),
        key=lambda flow: (flow.effective_date or date.min, flow.created_at),
    )
    return_flows = [
        flow for flow in dated_flows if flow.flow_type == RealEstateCashFlow.FlowType.CAPITAL_RETURN
    ]
    net_profit_obtained = sum(
        (
            net_profit(
                flow.amount,
                flow.withholding_rate if flow.withholding_rate is not None else effective_rate,
            )
            for flow in dated_flows
            if flow.flow_type == RealEstateCashFlow.FlowType.PROFIT
        ),
        Decimal("0"),
    )
    estimated_profit = (
        item.expected_profit
        if item.expected_profit is not None
        else max(Decimal("0"), contribution + reinvestment - returned)
        * (item.expected_irr or Decimal("0"))
        * (item.expected_term_months or 0)
        / Decimal("12")
    )
    net_estimated_profit = net_profit(estimated_profit, effective_rate)
    statuses: dict[str, str] = {
        RealEstateInvestment.Status.ACTIVE: "Activo",
        RealEstateInvestment.Status.COMPLETED: "Completado",
        RealEstateInvestment.Status.DEFAULTED: "Impagado",
        RealEstateInvestment.Status.CANCELLED: "Cancelado",
    }
    return {
        "id": item.legacy_id,
        "nombre": item.name,
        "plataforma": provider_name(item),
        "estado": statuses.get(item.status, item.status),
        "capital_inicial": number(contribution + reinvestment),
        "capital_nuevo": number(contribution),
        "capital_devuelto": number(returned),
        "beneficio_obtenido": number(profit),
        "beneficio_obtenido_neto": number(net_profit_obtained),
        "beneficio_estimado": (
            number(item.expected_profit) if item.expected_profit is not None else None
        ),
        "beneficio_estimado_neto": number(net_estimated_profit),
        "tir": number(item.expected_irr) * 100,
        "meses": item.expected_term_months or 0,
        "fecha_inicio": item.start_date.isoformat(),
        "fecha_vencimiento": item.maturity_date.isoformat() if item.maturity_date else "",
        "fecha_devolucion": (
            return_flows[-1].effective_date.isoformat()
            if return_flows and return_flows[-1].effective_date
            else ""
        ),
        "movimientos": [
            {
                "id": str(flow.id),
                "tipo": flow.flow_type,
                "fecha": flow.effective_date.isoformat() if flow.effective_date else "",
                "importe": number(flow.amount),
                "nota": flow.source_note,
                "retencion_irpf_aplicada": (
                    number(
                        flow.withholding_rate
                        if flow.withholding_rate is not None
                        else effective_rate
                    )
                    if flow.flow_type == RealEstateCashFlow.FlowType.PROFIT
                    else None
                ),
            }
            for flow in dated_flows
        ],
        "origen": item.origin,
        "retencion_irpf": number(item.tax_rate) if item.tax_rate is not None else None,
        "moneda": item.currency,
    }
