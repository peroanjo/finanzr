from __future__ import annotations

from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any

from django.core.cache import cache
from django.http import Http404
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Account
from apps.api.context import workspace
from apps.api.instrument_queries import workspace_instrument
from apps.api.market_queries import (
    yahoo_ticker,
)
from apps.api.projection import number, select_identifier
from apps.api.transaction_queries import (
    selected_traded_account,
    transaction_calculation_rows,
)
from apps.market_data.fx import (
    CurrencyConversionError,
    normalize_currency,
    rates_to_base,
)
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    StockSplit,
)
from apps.market_data.yahoo import (
    MarketDataError,
)
from apps.market_data.yahoo import (
    chart as yahoo_chart,
)
from finanzr.domain.investment_performance import calculate_investment_performance

PERFORMANCE_KINDS = {
    "fund": (Instrument.Kind.FUND, Account.Kind.FUNDS, InstrumentIdentifier.Scheme.ISIN),
    "stock": (Instrument.Kind.STOCK, Account.Kind.STOCKS, InstrumentIdentifier.Scheme.ISIN),
    "crypto": (
        Instrument.Kind.CRYPTO,
        Account.Kind.CRYPTO,
        InstrumentIdentifier.Scheme.CRYPTO_SYMBOL,
    ),
}


def _performance_period(
    request: Request,
) -> tuple[str, str | None, str | None, date | None, date | None] | Response:
    range_name = request.query_params.get("range", "1y")
    if range_name not in {"6m", "1y", "2y"}:
        range_name = "1y"
    start = request.query_params.get("start")
    end = request.query_params.get("end")
    if bool(start) != bool(end):
        return Response({"error": _("You must provide both a start and an end date")}, status=400)
    if not start or not end:
        return range_name, None, None, None, None
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return Response({"error": _("The period does not contain valid dates")}, status=400)
    if start_date > end_date:
        return Response({"error": _("The start date must be before the end date")}, status=400)
    return "custom", start, end, start_date, end_date


def _performance_result_range(range_name: str, start: str | None, end: str | None) -> str:
    return f"{start}_{end}" if start and end else range_name


def _named_performance_bounds(range_name: str) -> tuple[date, date]:
    """Resolve preset ranges to stable inclusive calendar boundaries."""
    end = timezone.localdate()
    months = {"6m": 6, "1y": 12, "2y": 24}[range_name]
    month_index = end.year * 12 + end.month - 1 - months
    year, month = divmod(month_index, 12)
    start = end.replace(
        year=year,
        month=month + 1,
        day=min(end.day, monthrange(year, month + 1)[1]),
    )
    return start, end


def _stock_split_rows(request: Request) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    splits = (
        StockSplit.objects.filter(workspace=workspace(request))
        .select_related("instrument")
        .prefetch_related("instrument__identifiers")
    )
    for split in splits:
        identity = select_identifier(
            split.instrument.identifiers.all(), InstrumentIdentifier.Scheme.ISIN
        )
        if identity:
            rows.append(
                {
                    "isin": identity.value,
                    "fecha": split.effective_date.isoformat(),
                    "ratio": number(split.ratio),
                }
            )
    return rows


def investment_performance(request: Request, kind: str) -> Response:
    """Build historical performance for a workspace-scoped investment kind."""
    config = PERFORMANCE_KINDS.get(kind)
    if config is None:
        return Response({"error": _("The investment type is not valid")}, status=400)
    instrument_kind, _account_kind, identifier_scheme = config
    try:
        selected_account = selected_traded_account(request, kind)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    account_value = str(selected_account.id) if selected_account is not None else "all"

    period = _performance_period(request)
    if isinstance(period, Response):
        return period
    range_name, start, end, start_date, end_date = period
    current_workspace = workspace(request)
    base_currency = normalize_currency(current_workspace.base_currency)
    ignore_savebacks = (
        kind == "stock" and request.query_params.get("ignore_savebacks", "").casefold() == "true"
    )
    response_range = _performance_result_range(range_name, start, end)
    if start_date and end_date:
        timeline_start, timeline_end = start, end
    else:
        named_start, named_end = _named_performance_bounds(range_name)
        timeline_start, timeline_end = named_start.isoformat(), named_end.isoformat()
    cache_key = (
        f"investment-performance:v2:{current_workspace.pk}:{kind}:{account_value}:"
        f"{response_range}:{base_currency}:saveback={int(ignore_savebacks)}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    rows = transaction_calculation_rows(request, instrument_kind, selected_account)
    result_base: dict[str, Any] = {
        "range": response_range,
        "account_id": account_value,
        "base_currency": base_currency,
        "data": [],
    }
    if not rows:
        cache.set(cache_key, result_base, timeout=3600)
        return Response(result_base)

    asset_key = "symbol" if kind == "crypto" else "isin"
    assets = sorted({str(row.get(asset_key, "")) for row in rows if row.get(asset_key)})
    tickers: dict[str, str] = {}
    history_failed = False
    for asset in assets:
        try:
            instrument = workspace_instrument(request, identifier_scheme, asset)
            if getattr(instrument, "kind", instrument_kind) != instrument_kind:
                continue
            tickers[asset] = yahoo_ticker(instrument)
        except (Http404, MarketDataError):
            # Missing identifiers/tickers are isolated to that instrument.
            history_failed = True
            continue

    interval = "1wk" if range_name == "2y" else "1d"
    if start_date and end_date and (end_date - start_date).days > 540:
        interval = "1wk"

    def load_history(asset: str, ticker: str) -> tuple[str, dict[str, float], bool]:
        history_key = (
            f"investment-history:{current_workspace.pk}:{kind}:{ticker}:"
            f"{base_currency}:{response_range}:{interval}"
        )
        history = cache.get(history_key)
        if history is not None:
            return asset, history, False
        try:
            meta, points = yahoo_chart(
                ticker,
                range_name=range_name if range_name != "custom" else "1y",
                interval=interval,
                start=start,
                end=end,
            )
            currency = normalize_currency(meta.get("currency") or "EUR")
            dated_points = [
                (date.fromisoformat(str(point["fecha"])), point)
                for point in points
                if point.get("fecha") and point.get("precio", point.get("close")) not in (None, "")
            ]
            if start_date and end_date:
                dated_points = [
                    (point_date, point)
                    for point_date, point in dated_points
                    if start_date <= point_date <= end_date
                ]
            if not dated_points:
                return asset, {}, False
            conversions = rates_to_base(
                currency,
                base_currency,
                [point_date for point_date, _point in dated_points],
                workspace=current_workspace,
            )
            converted: dict[str, float] = {}
            for point_date, point in dated_points:
                raw_price = point.get("precio", point.get("close"))
                conversion = conversions.get(point_date)
                if conversion is None or raw_price in (None, ""):
                    continue
                converted[point_date.isoformat()] = round(
                    float(str(raw_price)) * float(conversion.rate), 8
                )
            cache.set(history_key, converted, timeout=3600)
            return asset, converted, False
        except (MarketDataError, CurrencyConversionError, ValueError, KeyError):
            return asset, {}, True

    histories: dict[str, dict[str, float]] = {}
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(tickers)))) as executor:
        futures = {
            executor.submit(load_history, asset, ticker): asset for asset, ticker in tickers.items()
        }
        for future in as_completed(futures):
            asset, history, failed = future.result()
            histories[asset] = history
            history_failed = history_failed or failed

    split_rows = _stock_split_rows(request) if kind == "stock" else ()
    result_base["data"] = [
        {
            "date": point["fecha"],
            "value": point["valor"],
            "invested": point["invertido"],
            "pnl": point["pnl"],
            "pnl_percent": point["pnl_pct"],
        }
        for point in calculate_investment_performance(
            rows,
            histories,
            kind=kind,
            account_id=account_value,
            splits=split_rows,
            ignore_savebacks=ignore_savebacks,
            timeline_start=timeline_start,
            timeline_end=timeline_end,
        )
    ]
    if not history_failed:
        cache.set(cache_key, result_base, timeout=3600)
    return Response(result_base)


@api_view(["GET"])
def investment_performance_view(request: Request, kind: str) -> Response:
    return investment_performance(request, kind)
