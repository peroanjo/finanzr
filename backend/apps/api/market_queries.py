from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework.request import Request

from apps.api.context import workspace
from apps.api.instrument_queries import workspace_instruments
from apps.api.market_data_projection import (
    price_calculation_row,
    price_row,
)
from apps.api.projection import select_identifier
from apps.market_data.fx import (
    normalize_currency,
    rate_to_base,
)
from apps.market_data.locking import instrument_identifier_lock_keys, lock_logical_keys
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    MarketPrice,
    WorkspaceMarketPriceOverride,
)
from apps.market_data.yahoo import (
    MarketDataError,
    search,
)
from apps.workspaces.models import Workspace


def _selected_market_prices(
    request: Request, kind: str
) -> tuple[Workspace, list[MarketPrice | WorkspaceMarketPriceOverride]]:
    current_workspace = workspace(request)
    instruments = workspace_instruments(request, kind)
    queryset = (
        MarketPrice.objects.select_related("instrument")
        .prefetch_related("instrument__identifiers")
        .filter(
            instrument__in=instruments,
            granularity=MarketPrice.Granularity.SPOT,
        )
        .order_by("instrument_id", "-quoted_at", "-created_at")
    )
    latest_by_instrument: dict[Any, MarketPrice] = {}
    for provider_price in queryset:
        latest_by_instrument.setdefault(provider_price.instrument_id, provider_price)
    overrides = (
        WorkspaceMarketPriceOverride.objects.select_related("instrument")
        .prefetch_related("instrument__identifiers")
        .filter(
            workspace=current_workspace,
            instrument__in=instruments,
        )
    )
    selected: dict[Any, MarketPrice | WorkspaceMarketPriceOverride] = dict(latest_by_instrument)
    for override in overrides:
        existing = selected.get(override.instrument_id)
        if existing is None or override.quoted_at >= existing.quoted_at:
            selected[override.instrument_id] = override
    return current_workspace, list(selected.values())


def price_rows(request: Request, kind: str) -> list[dict[str, Any]]:
    current_workspace, selected_prices = _selected_market_prices(request, kind)
    base_currency = normalize_currency(current_workspace.base_currency)

    rows = []
    for selected_price in selected_prices:
        conversion = rate_to_base(
            selected_price.currency,
            base_currency,
            selected_price.quoted_at.date(),
            workspace=current_workspace,
        )
        rows.append(
            price_row(
                selected_price,
                converted_price=selected_price.close * conversion.rate,
                base_currency=base_currency,
                fx_rate=conversion.rate,
                fx_rate_date=conversion.rate_date,
                fx_source=conversion.source,
            )
        )
    return rows


def calculation_price_rows(request: Request, kind: str) -> list[dict[str, Any]]:
    """Return the private transitional price shape used by domain calculators."""
    current_workspace, selected_prices = _selected_market_prices(request, kind)
    base_currency = normalize_currency(current_workspace.base_currency)
    rows = []
    for selected_price in selected_prices:
        conversion = rate_to_base(
            selected_price.currency,
            base_currency,
            selected_price.quoted_at.date(),
            workspace=current_workspace,
        )
        rows.append(
            price_calculation_row(
                selected_price,
                converted_price=selected_price.close * conversion.rate,
                base_currency=base_currency,
                fx_rate=conversion.rate,
                fx_rate_date=conversion.rate_date,
                fx_source=conversion.source,
            )
        )
    return rows


def yahoo_ticker(instrument: Instrument) -> str:
    identity = select_identifier(instrument.identifiers.all(), InstrumentIdentifier.Scheme.YAHOO)
    if identity and identity.value:
        return identity.value
    isin = select_identifier(instrument.identifiers.all(), InstrumentIdentifier.Scheme.ISIN)
    if not isin:
        raise MarketDataError(_("The instrument does not have a ticker configured"))
    found = search(isin.value)
    ticker = str(found.get("ticker", "")).strip()
    if not ticker or len(ticker) > 120:
        raise MarketDataError(_("The market-data provider returned an invalid ticker"))
    with transaction.atomic():
        lock_logical_keys(
            [
                *instrument_identifier_lock_keys(InstrumentIdentifier.Scheme.ISIN, isin.value),
                *instrument_identifier_lock_keys(InstrumentIdentifier.Scheme.YAHOO, ticker),
            ]
        )
        locked_instrument = Instrument.objects.select_for_update().get(pk=instrument.pk)
        current = select_identifier(
            InstrumentIdentifier.objects.select_for_update().filter(
                instrument=locked_instrument,
                scheme=InstrumentIdentifier.Scheme.YAHOO,
            ),
            InstrumentIdentifier.Scheme.YAHOO,
        )
        if current and current.value:
            return current.value
        ticker_owner = (
            InstrumentIdentifier.objects.select_for_update()
            .filter(scheme=InstrumentIdentifier.Scheme.YAHOO, value=ticker, venue="")
            .exclude(instrument=locked_instrument)
            .first()
        )
        if ticker_owner:
            raise MarketDataError(_("The ticker already belongs to another asset"))
        InstrumentIdentifier.objects.update_or_create(
            instrument=locked_instrument,
            scheme=InstrumentIdentifier.Scheme.YAHOO,
            defaults={"value": ticker, "venue": ""},
        )
    return ticker
