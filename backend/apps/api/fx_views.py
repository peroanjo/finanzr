from __future__ import annotations

from datetime import date
from decimal import InvalidOperation
from typing import Any
from uuid import UUID

from django.core.cache import cache
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.api.legacy import number
from apps.api.views import decimal, forbidden_if_readonly, payload, workspace
from apps.market_data.fx import (
    CurrencyConversionError,
    historical_rates_to_base,
    normalize_currency,
    rate_to_base,
)
from apps.market_data.models import FxRate, WorkspaceFxOverride


@api_view(["GET", "POST"])
def fx_rates(request: Request) -> Response:
    current_workspace = workspace(request)

    def rate_row(obj: FxRate | WorkspaceFxOverride, scope: str) -> dict[str, Any]:
        return {
            "id": obj.pk,
            "quote_currency": obj.quote_currency,
            "base_currency": obj.base_currency,
            "rate_date": obj.rate_date.isoformat(),
            "rate": number(obj.rate),
            "source": obj.source,
            "scope": scope,
        }

    if request.method == "POST":
        if denied := forbidden_if_readonly(request):
            return denied
        data = payload(request)
        try:
            quote = normalize_currency(data.get("quote_currency") or "USD")
            base = normalize_currency(data.get("base_currency") or current_workspace.base_currency)
        except CurrencyConversionError as exc:
            return Response({"error": str(exc)}, status=400)
        if quote == base:
            return Response({"error": _("Currencies must be different")}, status=400)
        rate_date_str = str(data.get("rate_date") or date.today().isoformat())[:10]
        try:
            rate_date = date.fromisoformat(rate_date_str)
        except ValueError:
            return Response({"error": _("Invalid exchange rate date")}, status=400)
        try:
            val = decimal(data.get("rate"))
            if val <= 0:
                return Response({"error": _("Rate must be greater than zero")}, status=400)
        except (ValueError, TypeError, InvalidOperation):
            return Response({"error": _("Invalid exchange rate value")}, status=400)

        fx_obj, _created = WorkspaceFxOverride.objects.update_or_create(
            workspace=current_workspace,
            quote_currency=quote,
            base_currency=base,
            rate_date=rate_date,
            defaults={"rate": val, "source": "manual"},
        )
        cache.clear()
        return Response(rate_row(fx_obj, "workspace"), status=201 if _created else 200)

    provider_rates = FxRate.objects.all()
    overrides = WorkspaceFxOverride.objects.filter(workspace=current_workspace)
    try:
        if query_quote := request.query_params.get("quote_currency"):
            normalized_quote = normalize_currency(query_quote)
            provider_rates = provider_rates.filter(quote_currency=normalized_quote)
            overrides = overrides.filter(quote_currency=normalized_quote)
        if query_base := request.query_params.get("base_currency"):
            normalized_base = normalize_currency(query_base)
            provider_rates = provider_rates.filter(base_currency=normalized_base)
            overrides = overrides.filter(base_currency=normalized_base)
    except CurrencyConversionError as exc:
        return Response({"error": str(exc)}, status=400)
    if source := request.query_params.get("source"):
        provider_rates = provider_rates.filter(source=source)
        overrides = overrides.filter(source=source)
    if search := request.query_params.get("search"):
        search = search.strip().upper()
        currency_search = Q(quote_currency__icontains=search) | Q(base_currency__icontains=search)
        provider_rates = provider_rates.filter(currency_search)
        overrides = overrides.filter(currency_search)

    rows = [rate_row(obj, "provider") for obj in provider_rates.order_by("-rate_date")[:500]]
    rows.extend(rate_row(obj, "workspace") for obj in overrides.order_by("-rate_date")[:500])
    rows.sort(key=lambda row: (row["rate_date"], str(row["id"])), reverse=True)
    return Response(rows[:500])


@api_view(["PUT", "PATCH", "DELETE"])
def fx_rate_detail(request: Request, rate_id: UUID) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    current_workspace = workspace(request)
    obj = WorkspaceFxOverride.objects.filter(workspace=current_workspace, pk=rate_id).first()
    provider = None if obj else FxRate.objects.filter(pk=rate_id).first()
    if obj is None and provider is None:
        return Response({"error": _("Exchange rate not found")}, status=404)
    if request.method == "DELETE":
        if obj is None:
            return Response({"error": _("Provider rates cannot be deleted")}, status=400)
        if request.query_params.get("scope") == "pair":
            deleted_count, _deleted_details = WorkspaceFxOverride.objects.filter(
                workspace=current_workspace,
                quote_currency=obj.quote_currency,
                base_currency=obj.base_currency,
            ).delete()
            cache.clear()
            return Response({"ok": True, "deleted_count": deleted_count})
        obj.delete()
        cache.clear()
        return Response({"ok": True, "deleted_count": 1})

    data = payload(request)
    if obj is None:
        assert provider is not None
        obj = WorkspaceFxOverride(
            workspace=current_workspace,
            quote_currency=provider.quote_currency,
            base_currency=provider.base_currency,
            rate_date=provider.rate_date,
            rate=provider.rate,
            source="manual",
        )
    if "rate" in data:
        try:
            val = decimal(data["rate"])
            if val <= 0:
                return Response({"error": _("Rate must be greater than zero")}, status=400)
            obj.rate = val
        except (ValueError, TypeError, InvalidOperation):
            return Response({"error": _("Invalid exchange rate value")}, status=400)

    try:
        if "quote_currency" in data:
            obj.quote_currency = normalize_currency(data["quote_currency"])
        if "base_currency" in data:
            obj.base_currency = normalize_currency(data["base_currency"])
    except CurrencyConversionError as exc:
        return Response({"error": str(exc)}, status=400)
    if obj.quote_currency == obj.base_currency:
        return Response({"error": _("Currencies must be different")}, status=400)
    if "rate_date" in data:
        try:
            obj.rate_date = date.fromisoformat(str(data["rate_date"])[:10])
        except ValueError:
            return Response({"error": _("Invalid exchange rate date")}, status=400)
    obj.source = "manual"
    try:
        if provider is not None:
            obj, _created = WorkspaceFxOverride.objects.update_or_create(
                workspace=current_workspace,
                quote_currency=obj.quote_currency,
                base_currency=obj.base_currency,
                rate_date=obj.rate_date,
                defaults={"rate": obj.rate, "source": "manual"},
            )
        else:
            obj.save()
    except IntegrityError:
        return Response(
            {"error": _("An override already exists for this pair and date")},
            status=400,
        )
    cache.clear()
    return Response(
        {
            "id": obj.pk,
            "quote_currency": obj.quote_currency,
            "base_currency": obj.base_currency,
            "rate_date": obj.rate_date.isoformat(),
            "rate": number(obj.rate),
            "source": obj.source,
            "scope": "workspace",
        }
    )


@api_view(["POST"])
def fetch_fx_rates(request: Request) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    pairs = set(
        FxRate.objects.order_by("quote_currency", "base_currency")
        .values_list("quote_currency", "base_currency")
        .distinct()
    )
    pairs.update(
        WorkspaceFxOverride.objects.filter(workspace=workspace(request)).values_list(
            "quote_currency", "base_currency"
        )
    )
    today_date = timezone.localdate()
    updated_count = 0
    errors = []
    for quote, base in sorted(pairs):
        try:
            rate_to_base(quote, base, today_date)
            updated_count += 1
        except CurrencyConversionError as exc:
            errors.append(f"{quote}/{base}: {exc}")

    cache.clear()
    return Response(
        {
            "ok": True,
            "updated_count": updated_count,
            "errors": errors,
        }
    )


@api_view(["GET"])
def fx_rate_chart(request: Request) -> Response:
    """Return read-only Yahoo history for the requested currency pair."""
    from_currency = request.query_params.get("from")
    to_currency = request.query_params.get("to")
    if not from_currency or not to_currency:
        return Response({"error": _("Both currencies are required")}, status=400)
    start_param = request.query_params.get("start")
    end_param = request.query_params.get("end")
    if bool(start_param) != bool(end_param):
        return Response({"error": _("You must provide both a start and an end date")}, status=400)
    start_date = None
    end_date = None
    if start_param and end_param:
        try:
            start_date = date.fromisoformat(start_param[:10])
            end_date = date.fromisoformat(end_param[:10])
        except ValueError:
            return Response({"error": _("The period does not contain valid dates")}, status=400)
        if start_date > end_date:
            return Response({"error": _("The start date must be before the end date")}, status=400)
    try:
        range_name, points = historical_rates_to_base(
            from_currency,
            to_currency,
            request.query_params.get("range", "1y"),
            start=start_date,
            end=end_date,
        )
    except CurrencyConversionError as exc:
        return Response({"error": str(exc)}, status=502)
    return Response(
        {
            "from_currency": normalize_currency(from_currency),
            "to_currency": normalize_currency(to_currency),
            "range": range_name,
            "data": [
                {"fecha": point.rate_date.isoformat(), "rate": number(point.rate)}
                for point in points
            ],
        }
    )


@api_view(["GET"])
def fx_convert(request: Request) -> Response:
    try:
        raw_amount = request.query_params.get("amount", "1")
        amount_val = decimal(raw_amount)
    except (ValueError, TypeError, InvalidOperation):
        return Response({"error": _("Invalid amount")}, status=400)

    current_workspace = workspace(request)
    try:
        quote = normalize_currency(request.query_params.get("from", "USD"))
        base = normalize_currency(request.query_params.get("to", current_workspace.base_currency))
    except CurrencyConversionError as exc:
        return Response({"error": str(exc)}, status=400)
    rate_date_param = request.query_params.get("date")
    try:
        calc_date = date.fromisoformat(rate_date_param[:10]) if rate_date_param else date.today()
    except (ValueError, TypeError):
        return Response({"error": _("Invalid exchange rate date")}, status=400)

    try:
        conversion = rate_to_base(
            quote,
            base,
            calc_date,
            persist=False,
            workspace=current_workspace,
        )
        converted_amount = amount_val * conversion.rate
        return Response(
            {
                "from_currency": quote,
                "to_currency": base,
                "original_amount": number(amount_val),
                "converted_amount": number(converted_amount),
                "rate": number(conversion.rate),
                "rate_date": conversion.rate_date.isoformat(),
                "source": conversion.source,
            }
        )
    except CurrencyConversionError as exc:
        return Response({"error": str(exc)}, status=404)
