"""Historical FX conversion helpers used by imports and portfolio calculations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db.models import Case, IntegerField, QuerySet, Value, When
from django.utils.translation import gettext_lazy as _

from .models import FxRate, WorkspaceFxOverride
from .yahoo import MarketDataError
from .yahoo import chart as yahoo_chart

if TYPE_CHECKING:
    from apps.workspaces.models import Workspace

__all__ = ["MarketDataError"]


class CurrencyConversionError(ValueError):
    """Raised when a transaction cannot be converted reproducibly."""


@dataclass(frozen=True)
class FxConversion:
    rate: Decimal
    rate_date: date
    source: str


@dataclass(frozen=True)
class FxHistoryPoint:
    """A read-only market close for a currency pair."""

    rate_date: date
    rate: Decimal


def normalize_currency(value: object, default: str = "EUR") -> str:
    """Return an ISO-like currency code while preserving the GBp quote unit."""
    raw = str(value or default).strip()
    if not raw:
        raw = default
    if raw in {"GBp", "GBX", "gbp", "gbx"}:
        return "GBp"
    normalized = raw.upper()
    if not re.fullmatch(r"[A-Z]{3}", normalized):
        raise CurrencyConversionError(_("Currency codes must contain exactly three letters"))
    return normalized


def _pair_currency(value: str) -> tuple[str, Decimal]:
    if value == "GBp":
        return "GBP", Decimal("0.01")
    return value, Decimal("1")


def _pair_details(quote: str, base: str) -> tuple[str, str, Decimal]:
    quote_pair, quote_scale = _pair_currency(quote)
    base_pair, base_scale = _pair_currency(base)
    return quote_pair, base_pair, quote_scale / base_scale


def _provider_priority(queryset: QuerySet[FxRate]) -> QuerySet[FxRate]:
    """Prefer Yahoo, then use a stable source/creation ordering."""
    return queryset.annotate(
        source_priority=Case(
            When(source="yahoo", then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by("source_priority", "source", "created_at", "pk")


def _stored_conversion(
    quote: str,
    base: str,
    requested_date: date,
    *,
    workspace: Workspace | None,
) -> FxConversion | None:
    """Resolve an exact or recent stored rate using the documented precedence."""
    if workspace is not None:
        overrides = WorkspaceFxOverride.objects.filter(
            workspace=workspace,
            quote_currency=quote,
            base_currency=base,
            rate_date__lte=requested_date,
            rate_date__gte=requested_date - timedelta(days=7),
        ).order_by("-rate_date", "-updated_at", "pk")
        if override := overrides.first():
            return FxConversion(override.rate, override.rate_date, override.source)
        inverse_overrides = WorkspaceFxOverride.objects.filter(
            workspace=workspace,
            quote_currency=base,
            base_currency=quote,
            rate_date__lte=requested_date,
            rate_date__gte=requested_date - timedelta(days=7),
        ).order_by("-rate_date", "-updated_at", "pk")
        if inverse_override := inverse_overrides.first():
            return FxConversion(
                Decimal("1") / inverse_override.rate,
                inverse_override.rate_date,
                inverse_override.source,
            )

    quote_pair, base_pair, scale = _pair_details(quote, base)
    providers = FxRate.objects.filter(
        quote_currency=quote_pair,
        base_currency=base_pair,
        rate_date__lte=requested_date,
        rate_date__gte=requested_date - timedelta(days=7),
    )
    latest_date = providers.order_by("-rate_date").values_list("rate_date", flat=True).first()
    if latest_date is not None:
        provider = _provider_priority(providers.filter(rate_date=latest_date)).first()
        if provider is not None:
            return FxConversion(provider.rate * scale, provider.rate_date, provider.source)

    inverse_providers = FxRate.objects.filter(
        quote_currency=base_pair,
        base_currency=quote_pair,
        rate_date__lte=requested_date,
        rate_date__gte=requested_date - timedelta(days=7),
    )
    inverse_date = (
        inverse_providers.order_by("-rate_date").values_list("rate_date", flat=True).first()
    )
    if inverse_date is None:
        return None
    inverse_provider = _provider_priority(inverse_providers.filter(rate_date=inverse_date)).first()
    if inverse_provider is None:
        return None
    return FxConversion(
        Decimal("1") / inverse_provider.rate * scale,
        inverse_provider.rate_date,
        inverse_provider.source,
    )


def historical_rates_to_base(
    quote_currency: object,
    base_currency: object,
    range_name: str = "1y",
    *,
    start: date | None = None,
    end: date | None = None,
) -> tuple[str, list[FxHistoryPoint]]:
    """Load Yahoo closes for a pair without adding them to ``FxRate`` records."""
    quote = normalize_currency(quote_currency)
    base = normalize_currency(base_currency)
    supported_ranges = {"1m", "6m", "1y", "2y"}
    selected_range = (
        "custom" if start and end else (range_name if range_name in supported_ranges else "1y")
    )
    if quote == base:
        return selected_range, [FxHistoryPoint(end or date.today(), Decimal("1"))]

    quote_pair, base_pair, scale = _pair_details(quote, base)
    custom_days = (end - start).days if start and end else 0
    interval = "1wk" if selected_range == "2y" or custom_days > 400 else "1d"
    last_error: Exception | None = None
    for ticker, inverse in (
        (f"{quote_pair}{base_pair}=X", False),
        (f"{base_pair}{quote_pair}=X", True),
    ):
        try:
            chart_kwargs = {"interval": interval}
            if start and end:
                chart_kwargs.update(start=start.isoformat(), end=end.isoformat())
            else:
                chart_kwargs["range_name"] = selected_range
            _meta, points = yahoo_chart(ticker, **chart_kwargs)
        except MarketDataError as exc:
            last_error = exc
            continue
        history = []
        for point in points:
            if point.get("precio") in (None, ""):
                continue
            rate = Decimal(str(point["precio"]))
            if rate <= 0:
                continue
            history.append(
                FxHistoryPoint(
                    date.fromisoformat(str(point["fecha"])),
                    (Decimal("1") / rate if inverse else rate) * scale,
                )
            )
        if history:
            return selected_range, history

    detail = f" ({last_error})" if last_error else ""
    raise CurrencyConversionError(
        _("No exchange rate history is available for %(quote)s/%(base)s%(detail)s")
        % {"quote": quote, "base": base, "detail": detail}
    )


def _fetch_pair_rate(
    quote_currency: str,
    base_currency: str,
    requested_date: date,
) -> FxConversion:
    """Fetch the closest market close on or before a requested date."""
    quote, base, scale = _pair_details(quote_currency, base_currency)
    if quote == base:
        return FxConversion(scale, requested_date, "identity")

    start = requested_date - timedelta(days=14)
    end = requested_date + timedelta(days=1)
    candidates = ((f"{quote}{base}=X", False), (f"{base}{quote}=X", True))
    last_error: Exception | None = None
    for ticker, inverse in candidates:
        try:
            _meta, points = yahoo_chart(
                ticker,
                start=start.isoformat(),
                end=end.isoformat(),
                interval="1d",
            )
        except MarketDataError as exc:
            last_error = exc
            continue
        usable = [
            (date.fromisoformat(str(point["fecha"])), Decimal(str(point["precio"])))
            for point in points
            if point.get("precio") not in (None, "")
        ]
        usable = [point for point in usable if point[0] <= requested_date and point[1] > 0]
        if not usable:
            continue
        rate_date, rate = max(usable, key=lambda point: point[0])
        if inverse:
            rate = Decimal("1") / rate
        return FxConversion(rate * scale, rate_date, "yahoo")

    detail = f" ({last_error})" if last_error else ""
    raise CurrencyConversionError(
        _("No exchange rate is available for %(quote)s/%(base)s on %(date)s%(detail)s")
        % {
            "quote": quote_currency,
            "base": base_currency,
            "date": requested_date.isoformat(),
            "detail": detail,
        }
    )


def rates_to_base(
    quote_currency: object,
    base_currency: object,
    requested_dates: list[date],
    *,
    workspace: Workspace | None = None,
) -> dict[date, FxConversion]:
    """Resolve a whole historical series with one market-data request."""
    quote = normalize_currency(quote_currency)
    base = normalize_currency(base_currency)
    dates = sorted(set(requested_dates))
    if not dates:
        return {}
    if quote == base:
        return {value: FxConversion(Decimal("1"), value, "identity") for value in dates}

    quote_pair, base_pair, scale = _pair_details(quote, base)
    result: dict[date, FxConversion] = {}
    missing: list[date] = []
    for requested_date in dates:
        stored = _stored_conversion(quote, base, requested_date, workspace=workspace)
        if stored is None:
            missing.append(requested_date)
        else:
            result[requested_date] = stored
    if not missing:
        return result

    start = missing[0] - timedelta(days=14)
    end = missing[-1] + timedelta(days=1)
    points_by_date: dict[date, Decimal] = {}
    source = "yahoo"
    last_error: Exception | None = None
    for ticker, inverse in (
        (f"{quote_pair}{base_pair}=X", False),
        (f"{base_pair}{quote_pair}=X", True),
    ):
        try:
            _meta, points = yahoo_chart(
                ticker,
                start=start.isoformat(),
                end=end.isoformat(),
                interval="1d",
            )
        except MarketDataError as exc:
            last_error = exc
            continue
        for point in points:
            if point.get("precio") in (None, ""):
                continue
            point_date = date.fromisoformat(str(point["fecha"]))
            rate = Decimal(str(point["precio"]))
            if rate > 0:
                points_by_date[point_date] = Decimal("1") / rate if inverse else rate
        if points_by_date:
            break
    if not points_by_date:
        detail = f" ({last_error})" if last_error else ""
        raise CurrencyConversionError(
            _("No exchange rate is available for %(quote)s/%(base)s%(detail)s")
            % {"quote": quote, "base": base, "detail": detail}
        )

    for rate_date, rate in points_by_date.items():
        FxRate.objects.get_or_create(
            quote_currency=quote_pair,
            base_currency=base_pair,
            rate_date=rate_date,
            source=source,
            defaults={"rate": rate},
        )
    for requested_date in dates:
        if requested_date in result:
            continue
        exact = points_by_date.get(requested_date)
        if exact is None:
            prior = [
                value
                for value in points_by_date
                if requested_date - timedelta(days=7) <= value < requested_date
            ]
            if prior:
                selected_date = max(prior)
                exact = points_by_date[selected_date]
            else:
                raise CurrencyConversionError(
                    _("No exchange rate is available for %(quote)s/%(base)s on %(date)s")
                    % {
                        "quote": quote,
                        "base": base,
                        "date": requested_date.isoformat(),
                    }
                )
        else:
            selected_date = requested_date
        result[requested_date] = FxConversion(exact * scale, selected_date, source)
    return result


def rate_to_base(
    quote_currency: object,
    base_currency: object,
    requested_date: date,
    *,
    provided_rate: Decimal | None = None,
    provided_date: date | None = None,
    provided_source: str = "manual",
    persist: bool = True,
    workspace: Workspace | None = None,
) -> FxConversion:
    """Resolve a rate, persisting it only when it becomes part of recorded data."""
    quote = normalize_currency(quote_currency)
    base = normalize_currency(base_currency)
    if quote == base:
        return FxConversion(Decimal("1"), requested_date, "identity")
    if provided_rate is not None:
        if provided_rate <= 0:
            raise CurrencyConversionError(_("The exchange rate must be greater than zero"))
        effective_date = provided_date or requested_date
        if persist and workspace is not None:
            WorkspaceFxOverride.objects.update_or_create(
                workspace=workspace,
                quote_currency=quote,
                base_currency=base,
                rate_date=effective_date,
                defaults={"rate": provided_rate, "source": "manual"},
            )
        return FxConversion(provided_rate, effective_date, provided_source)

    stored = _stored_conversion(quote, base, requested_date, workspace=workspace)
    if stored:
        return stored

    fetched = _fetch_pair_rate(quote, base, requested_date)
    if not persist:
        return fetched
    quote_pair, base_pair, scale = _pair_details(quote, base)
    stored_rate, _created = FxRate.objects.get_or_create(
        quote_currency=quote_pair,
        base_currency=base_pair,
        rate_date=fetched.rate_date,
        source=fetched.source,
        defaults={"rate": fetched.rate / scale},
    )
    return FxConversion(stored_rate.rate * scale, stored_rate.rate_date, stored_rate.source)


def convert_to_base(
    amount: Decimal,
    quote_currency: object,
    base_currency: object,
    requested_date: date,
    *,
    provided_rate: Decimal | None = None,
    provided_date: date | None = None,
    provided_source: str = "manual",
    workspace: Workspace | None = None,
) -> tuple[Decimal, FxConversion]:
    conversion = rate_to_base(
        quote_currency,
        base_currency,
        requested_date,
        provided_rate=provided_rate,
        provided_date=provided_date,
        provided_source=provided_source,
        workspace=workspace,
    )
    return amount * conversion.rate, conversion
