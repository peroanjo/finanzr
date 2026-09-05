from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

from rest_framework.request import Request

from apps.accounts.models import Account, AccountSnapshot
from apps.api.context import workspace
from apps.api.instrument_queries import workspace_instruments
from apps.api.market_data_projection import (
    instrument_calculation_row,
)
from apps.api.portfolio_queries import _summary_manual_assets
from apps.api.projection import identifier, number
from apps.api.real_estate_queries import real_estate_records
from apps.api.transaction_projection import (
    _transaction_calculation_row,
)
from apps.common.summary_preferences import (
    SUMMARY_SOURCE_KEYS,
    effective_summary_sources,
)
from apps.market_data.fx import (
    CurrencyConversionError,
    normalize_currency,
    rate_to_base,
)
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    MarketPrice,
    StockSplit,
    WorkspaceMarketPriceOverride,
)
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace
from finanzr.domain.crypto import calculate_crypto_positions
from finanzr.domain.funds import calculate_fund_positions
from finanzr.domain.net_worth import current_total, monthly_history
from finanzr.domain.real_estate import live_capital
from finanzr.domain.stocks import calculate_stock_positions


def _market_close_in_base(
    price: MarketPrice | WorkspaceMarketPriceOverride,
    current_workspace: Workspace,
    conversion_cache: dict[tuple[str, date], Decimal],
) -> Decimal | None:
    """Convert a stored market close without fabricating a missing FX history."""

    try:
        quote_currency = normalize_currency(price.currency)
        base_currency = normalize_currency(current_workspace.base_currency)
    except CurrencyConversionError:
        return None
    if quote_currency == base_currency:
        return price.close
    cache_key = (quote_currency, price.quoted_at.date())
    if cache_key not in conversion_cache:
        try:
            conversion_cache[cache_key] = rate_to_base(
                quote_currency,
                base_currency,
                price.quoted_at.date(),
                workspace=current_workspace,
            ).rate
        except CurrencyConversionError:
            return None
    return price.close * conversion_cache[cache_key]


def _traded_source_history(request: Request, kind: str) -> list[dict[str, Any]]:
    """Value traded positions at stored monthly closes when available.

    Market sources do not have synthetic history: months come from
    transactions and stored market closes. Valid closes are carried forward;
    an open position without a usable close is conservatively valued at its
    open base cost rather than being converted to zero.
    """

    current_workspace = workspace(request)
    instruments: list[Instrument] = list(workspace_instruments(request, kind))
    if not instruments:
        return []
    instrument_ids = [item.id for item in instruments]
    identity_scheme = (
        InstrumentIdentifier.Scheme.CRYPTO_SYMBOL
        if kind == "crypto"
        else InstrumentIdentifier.Scheme.ISIN
    )
    identity_by_instrument = {item.id: identifier(item, identity_scheme) for item in instruments}
    prices: list[MarketPrice] = list(
        MarketPrice.objects.filter(
            instrument_id__in=instrument_ids,
            granularity=MarketPrice.Granularity.SPOT,
        ).order_by("instrument_id", "quoted_at", "created_at")
    )
    overrides: list[WorkspaceMarketPriceOverride] = list(
        WorkspaceMarketPriceOverride.objects.filter(
            workspace=current_workspace, instrument_id__in=instrument_ids
        ).order_by("instrument_id", "quoted_at")
    )
    conversion_cache: dict[tuple[str, date], Decimal] = {}
    prices_by_month: dict[str, dict[str, tuple[date, Decimal]]] = {}

    def add_price(price: MarketPrice | WorkspaceMarketPriceOverride) -> None:
        key = identity_by_instrument.get(price.instrument_id, "")
        close_value = _market_close_in_base(price, current_workspace, conversion_cache)
        if not key or close_value is None:
            return
        month = price.quoted_at.date().isoformat()[:7]
        by_instrument = prices_by_month.setdefault(month, {})
        previous = by_instrument.get(key)
        if previous is None or price.quoted_at.date() >= previous[0]:
            by_instrument[key] = (price.quoted_at.date(), close_value)

    for price in prices:
        add_price(price)
    for override in overrides:
        add_price(override)

    transactions = list(
        Transaction.objects.filter(account__workspace=current_workspace, instrument__kind=kind)
        .select_related("account", "instrument")
        .prefetch_related("instrument__identifiers")
    )
    transaction_conversion_cache: dict[tuple[str, str, date], Decimal | None] = {}
    base_amounts: dict[Any, float | None] = {}
    invalid_instruments: set[Any] = set()
    for item in transactions:
        amount: float | None = (
            number(item.base_net_amount) if item.base_net_amount is not None else None
        )
        if amount is None:
            try:
                quote_currency = normalize_currency(item.currency)
                base_currency = normalize_currency(current_workspace.base_currency)
                if quote_currency == base_currency:
                    amount = number(item.net_amount)
                else:
                    cache_key = (quote_currency, base_currency, item.trade_date)
                    if cache_key not in transaction_conversion_cache:
                        try:
                            transaction_conversion_cache[cache_key] = rate_to_base(
                                quote_currency,
                                base_currency,
                                item.trade_date,
                                persist=False,
                                workspace=current_workspace,
                            ).rate
                        except CurrencyConversionError:
                            transaction_conversion_cache[cache_key] = None
                    rate = transaction_conversion_cache[cache_key]
                    amount = None if rate is None else number(item.net_amount * rate)
            except CurrencyConversionError:
                amount = None
        base_amounts[item.pk] = amount
        if amount is None:
            invalid_instruments.add(item.instrument_id)

    # An unresolved FX leg invalidates the whole instrument history. Keeping
    # earlier buys while dropping an unconverted sell would overstate holdings.
    valid_transactions = [
        item for item in transactions if item.instrument_id not in invalid_instruments
    ]
    valid_identity_keys = {
        identity_by_instrument[item.instrument_id]
        for item in valid_transactions
        if identity_by_instrument.get(item.instrument_id)
    }
    prices_by_month = {
        month: {key: value for key, value in values.items() if key in valid_identity_keys}
        for month, values in prices_by_month.items()
    }
    prices_by_month = {month: values for month, values in prices_by_month.items() if values}

    def effective_date(item: Transaction) -> date:
        if kind == "fund" and item.settlement_date is not None:
            return item.settlement_date
        return item.trade_date

    transaction_rows = []
    for item in valid_transactions:
        row = _transaction_calculation_row(item)
        row["importe_base"] = number(base_amounts[item.pk])
        transaction_rows.append(row)
    months = set(prices_by_month)
    months.update(effective_date(item).isoformat()[:7] for item in valid_transactions)
    if not months:
        return []

    fund_map = (
        {
            instrument_calculation_row(item)["isin"]: instrument_calculation_row(item)
            for item in instruments
        }
        if kind == "fund"
        else {}
    )
    split_rows: list[dict[str, Any]] = (
        [
            {
                "isin": identifier(split.instrument, InstrumentIdentifier.Scheme.ISIN),
                "fecha": split.effective_date.isoformat(),
                "ratio": number(split.ratio),
            }
            for split in StockSplit.objects.filter(
                workspace=current_workspace, instrument_id__in=instrument_ids
            )
            .select_related("instrument")
            .prefetch_related("instrument__identifiers")
        ]
        if kind == "stock"
        else []
    )
    ordered_months = sorted(months)
    result: list[dict[str, Any]] = []
    for month in ordered_months:
        month_end = date.fromisoformat(f"{month}-01")
        if month_end.month == 12:
            month_end = date(month_end.year, 12, 31)
        else:
            month_end = date(month_end.year, month_end.month + 1, 1) - timedelta(days=1)
        prices_as_of: dict[str, Decimal] = {}
        for price_month in ordered_months:
            if price_month > month:
                break
            prices_as_of.update(
                {key: value for key, (_date, value) in prices_by_month.get(price_month, {}).items()}
            )
        rows_as_of = [
            row
            for row in transaction_rows
            if str(
                (
                    row.get("fecha_liquidacion")
                    if kind == "fund" and row.get("fecha_liquidacion")
                    else row.get("fecha_operacion")
                )
                or ""
            )[:10]
            <= month_end.isoformat()
        ]
        if kind == "fund":
            positions = calculate_fund_positions(rows_as_of, fund_map, prices_as_of)
        elif kind == "stock":
            positions = calculate_stock_positions(
                rows_as_of,
                prices_as_of,
                [item for item in split_rows if item["fecha"] <= month_end.isoformat()],
            )
        else:
            positions = calculate_crypto_positions(rows_as_of, prices_as_of)
        # A missing close is not a zero valuation.  Keep the open position at
        # its base cost until a valid close (or FX conversion) is available;
        # this is conservative and avoids manufacturing a P&L loss.
        value = 0.0
        for position in positions:
            marked_value = position.get("valor_actual")
            if marked_value not in (None, ""):
                value += number(marked_value)
            elif kind == "fund":
                value += number(position.get("total_invertido"))
            else:
                value += number(position.get("coste_total"))
        contribution = 0.0
        for item in valid_transactions:
            if effective_date(item).isoformat()[:7] != month:
                continue
            amount = number(base_amounts[item.pk])
            if item.is_saveback:
                continue
            if item.cash_flow_type == Transaction.CashFlowType.CONTRIBUTION:
                contribution += amount
            elif item.cash_flow_type == Transaction.CashFlowType.WITHDRAWAL:
                contribution -= amount
            elif item.operation_type == Transaction.OperationType.BUY:
                contribution += amount
            elif item.operation_type == Transaction.OperationType.SELL:
                contribution -= amount
        result.append(
            {
                "fecha": month,
                "cuenta_id": f"summary:{kind}",
                "valor": value,
                "aporte": contribution,
            }
        )
    return result


def _summary_snapshot_row(snapshot: AccountSnapshot) -> dict[str, Any]:
    """Keep summary's internal calculation keys independent of legacy IDs."""

    value_key = "saldo" if snapshot.account.kind == Account.Kind.SAVINGS else "valor"
    return {
        "fecha": snapshot.date.isoformat(),
        "cuenta_id": str(snapshot.account_id),
        value_key: number(
            snapshot.base_value if snapshot.base_value is not None else snapshot.value
        ),
        "aporte": number(
            snapshot.base_contribution
            if snapshot.base_contribution is not None
            else snapshot.contribution
        ),
        "intereses": number(
            snapshot.base_earnings if snapshot.base_earnings is not None else snapshot.earnings
        ),
    }


def _overview_calculation(request: Request) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    current_workspace = workspace(request)
    user = cast(User, request.user)
    included_sources, source_scope = effective_summary_sources(user, current_workspace)
    properties = real_estate_records(request)
    manual_assets = _summary_manual_assets(request, properties)
    all_savings = [
        _summary_snapshot_row(x)
        for x in AccountSnapshot.objects.select_related("account").filter(
            account__workspace=current_workspace, account__kind=Account.Kind.SAVINGS
        )
    ]
    all_investments = [
        _summary_snapshot_row(x)
        for x in AccountSnapshot.objects.select_related("account").filter(
            account__workspace=current_workspace, account__kind=Account.Kind.MANUAL_INVESTMENT
        )
    ]
    savings = all_savings if "savings" in included_sources else []
    investments = all_investments if "manual_investments" in included_sources else []
    selected_properties = properties if "crowdfunding" in included_sources else []
    source_series: dict[str, list[dict[str, Any]]] = {}
    for source_key, kind in (("funds", "fund"), ("stocks", "stock"), ("crypto", "crypto")):
        if source_key in included_sources:
            source_series[source_key] = _traded_source_history(request, kind)
    if "manual_assets" in included_sources:
        source_series["manual_assets"] = [
            {
                "fecha": item.valued_at.isoformat(),
                "cuenta_id": f"manual:{item.pk}",
                "valor": number(item.value),
                "aporte": 0,
            }
            for item in manual_assets
        ]
    history = monthly_history(
        savings,
        investments,
        selected_properties,
        source_series=source_series,
    )
    totals: dict[str, float] = {
        "savings": current_total(savings, "saldo"),
        "manual_investments": current_total(investments, "valor"),
        "crowdfunding": sum((live_capital(item) for item in selected_properties), 0.0),
        "funds": number(source_series.get("funds", [])[-1].get("valor"))
        if source_series.get("funds")
        else 0.0,
        "stocks": number(source_series.get("stocks", [])[-1].get("valor"))
        if source_series.get("stocks")
        else 0.0,
        "crypto": number(source_series.get("crypto", [])[-1].get("valor"))
        if source_series.get("crypto")
        else 0.0,
        "manual_assets": sum((number(item.value) for item in manual_assets), 0.0)
        if "manual_assets" in included_sources
        else 0.0,
    }
    totals = {key: (value if key in included_sources else 0.0) for key, value in totals.items()}
    latest_change = (
        float(history[-1]["total"]) - float(history[-2]["total"]) if len(history) > 1 else 0
    )
    total_interest = sum(number(item.get("intereses")) for item in savings + investments)
    breakdown = [
        {"key": key, "value": round(totals.get(key, 0.0), 2), "included": key in included_sources}
        for key in SUMMARY_SOURCE_KEYS
    ]
    summary_payload = {
        "total_savings": round(totals["savings"], 2),
        "total_investments": round(totals["manual_investments"], 2),
        "total_real_estate": round(totals["crowdfunding"], 2),
        "net_worth": round(sum(totals.values()), 2),
        "net_worth_change": round(latest_change, 2),
        "total_interest": round(total_interest, 2),
        "summary_sources": included_sources,
        "summary_sources_scope": source_scope,
        "source_breakdown": breakdown,
    }
    return summary_payload, history
