from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.api.context import workspace
from apps.api.instrument_queries import workspace_instruments
from apps.api.market_queries import price_list, yahoo_ticker
from apps.api.permissions import forbidden_if_readonly
from apps.api.projection import number
from apps.api.request_data import payload
from apps.api.schemas import (
    PriceRequestSerializer,
    StockSplitRequestSerializer,
)
from apps.market_data.fx import (
    CurrencyConversionError,
    normalize_currency,
    rate_to_base,
    rates_to_base,
)
from apps.market_data.models import (
    Instrument,
    MarketPrice,
    StockSplit,
    WorkspaceMarketPriceOverride,
)
from apps.market_data.yahoo import (
    MarketDataError,
    quote_price,
)
from apps.market_data.yahoo import (
    chart as yahoo_chart,
)
from apps.users.models import User


@api_view(["GET"])
def fund_prices(request: Request) -> Response:
    return price_list(request, "fund")


@api_view(["GET"])
def stock_prices(request: Request) -> Response:
    return price_list(request, "stock")


@api_view(["GET"])
def crypto_prices(request: Request) -> Response:
    return price_list(request, "crypto")


def update_price(request: Request, instrument_id: UUID, kind: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    current_workspace = workspace(request)
    instrument = (
        Instrument.objects.filter(pk=instrument_id, kind=kind)
        .filter(
            Q(workspace_links__workspace=current_workspace)
            | Q(transactions__account__workspace=current_workspace)
        )
        .first()
    )
    if instrument is None:
        raise Http404
    serializer = PriceRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    data = cast(dict[str, Any], serializer.validated_data)
    try:
        value = data["close"]
        currency = normalize_currency(
            data.get("currency") or instrument.quote_currency or current_workspace.base_currency
        )
    except (ValueError, CurrencyConversionError) as exc:
        return Response({"error": str(exc)}, status=400)
    if value < 0:
        return Response({"error": _("The price cannot be negative")}, status=400)
    now = timezone.now()
    WorkspaceMarketPriceOverride.objects.update_or_create(
        workspace=workspace(request),
        instrument=instrument,
        defaults={
            "quoted_at": now,
            "close": value,
            "currency": currency,
            "source": "manual",
        },
    )
    cache.clear()
    return Response({"ok": True})


@api_view(["PUT"])
def fund_price_detail(request: Request, instrument_id: UUID) -> Response:
    return update_price(request, instrument_id, "fund")


@api_view(["PUT"])
def stock_price_detail(request: Request, instrument_id: UUID) -> Response:
    return update_price(request, instrument_id, "stock")


@api_view(["GET", "POST"])
def stock_splits(request: Request) -> Response:
    current_workspace = workspace(request)
    queryset = StockSplit.objects.filter(
        workspace=current_workspace,
        instrument__kind=Instrument.Kind.STOCK,
    )
    if request.method == "GET":
        return Response([_stock_split_row(split) for split in queryset])
    if denied := forbidden_if_readonly(request):
        return denied

    serializer = StockSplitRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = cast(dict[str, Any], serializer.validated_data)
    instrument = (
        workspace_instruments(request, Instrument.Kind.STOCK)
        .filter(pk=data["instrument_id"])
        .first()
    )
    if instrument is None:
        return Response(
            {"error": _("The instrument is not available in this workspace")}, status=400
        )

    with transaction.atomic():
        locked_instrument = Instrument.objects.select_for_update().get(pk=instrument.pk)
        split, _created = StockSplit.objects.select_for_update().update_or_create(
            workspace=current_workspace,
            instrument=locked_instrument,
            effective_date=data["effective_date"],
            defaults={
                "ratio": data["ratio"],
                "source": data["source"],
                "confirmed_by": cast(User, request.user),
            },
        )
    cache.clear()
    return Response(_stock_split_row(split), status=200)


@api_view(["DELETE"])
def stock_split_detail(request: Request, split_id: UUID) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    split = get_object_or_404(
        StockSplit.objects.filter(
            workspace=workspace(request),
            instrument__kind=Instrument.Kind.STOCK,
        ),
        pk=split_id,
    )
    split.delete()
    cache.clear()
    return Response({"ok": True})


def _stock_split_row(split: StockSplit) -> dict[str, Any]:
    """Return the native public representation of a stock split."""
    return {
        "id": str(split.id),
        "instrument_id": str(split.instrument_id),
        "effective_date": split.effective_date.isoformat(),
        "ratio": number(split.ratio),
        "source": split.source,
    }


def market_chart(request: Request, kind: str, instrument_id: UUID) -> Response:
    instrument = get_object_or_404(workspace_instruments(request, kind), pk=instrument_id)
    try:
        ticker = yahoo_ticker(instrument)
        interval = request.query_params.get("interval", "1d")
        meta, points = yahoo_chart(
            ticker,
            range_name=request.query_params.get("range", "1y"),
            interval=interval if interval in {"1d", "1wk", "1mo"} else "1d",
            start=request.query_params.get("start"),
            end=request.query_params.get("end"),
        )
        currency = normalize_currency(meta.get("currency") or "EUR")
        base_currency = normalize_currency(workspace(request).base_currency)
        try:
            conversions = rates_to_base(
                currency,
                base_currency,
                [date.fromisoformat(str(row["fecha"])) for row in points],
                workspace=workspace(request),
            )
        except CurrencyConversionError as exc:
            return Response({"error": str(exc)}, status=502)
        if kind == "fund":
            data = [
                {
                    "date": row["fecha"],
                    "close": round(
                        float(row["precio"])
                        * float(conversions[date.fromisoformat(row["fecha"])].rate),
                        6,
                    ),
                }
                for row in points
            ]
        else:
            data = [
                {
                    "date": row["fecha"],
                    **{
                        key: round(
                            float(row[key])
                            * float(conversions[date.fromisoformat(row["fecha"])].rate),
                            6,
                        )
                        for key in ("open", "high", "low", "close")
                    },
                }
                for row in points
            ]
        return Response(
            {
                "instrument_id": str(instrument.id),
                "ticker": ticker,
                "currency": currency,
                "base_currency": base_currency,
                "range": request.query_params.get("range", "1y"),
                "data": data,
            }
        )
    except MarketDataError as exc:
        return Response({"error": str(exc)}, status=502)


@api_view(["GET"])
def fund_chart(request: Request, instrument_id: UUID) -> Response:
    return market_chart(request, "fund", instrument_id)


@api_view(["GET"])
def stock_chart(request: Request, instrument_id: UUID) -> Response:
    return market_chart(request, "stock", instrument_id)


@api_view(["GET"])
def crypto_chart(request: Request, instrument_id: UUID) -> Response:
    return market_chart(request, "crypto", instrument_id)


def fetch_prices(request: Request, kind: str) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    instruments_qs = workspace_instruments(request, kind)
    base_currency = normalize_currency(workspace(request).base_currency)
    results = []
    for instrument in instruments_qs:
        result: dict[str, Any] = {
            "instrument_id": str(instrument.id),
            "base_close": None,
            "close": None,
            "currency": None,
            "ticker": None,
            "error": None,
        }
        try:
            ticker = yahoo_ticker(instrument)
            original, raw_currency = quote_price(ticker)
            currency = normalize_currency(raw_currency)
            if instrument.quote_currency != currency:
                instrument.quote_currency = currency
                instrument.save(update_fields=("quote_currency", "updated_at"))
            conversion = rate_to_base(
                currency,
                base_currency,
                timezone.localdate(),
                workspace=workspace(request),
            )
            conversion_rate = conversion.rate
            price_base = Decimal(str(original)) * conversion_rate
            MarketPrice.objects.filter(
                instrument=instrument, granularity="spot", source="yahoo"
            ).delete()
            MarketPrice.objects.create(
                instrument=instrument,
                quoted_at=timezone.now(),
                granularity="spot",
                close=original,
                currency=currency,
                source="yahoo",
            )
            result.update(
                ticker=ticker,
                base_close=number(round(price_base, 6)),
                close=number(original),
                currency=currency,
            )
        except (MarketDataError, CurrencyConversionError) as exc:
            result["error"] = str(exc)
        results.append(result)
    cache.clear()
    return Response({"results": results})


@api_view(["POST"])
def fetch_fund_prices(request: Request) -> Response:
    return fetch_prices(request, "fund")


@api_view(["POST"])
def fetch_stock_prices(request: Request) -> Response:
    return fetch_prices(request, "stock")


@api_view(["POST"])
def fetch_crypto_prices(request: Request) -> Response:
    return fetch_prices(request, "crypto")
