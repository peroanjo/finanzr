from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import QuerySet
from django.utils.translation import gettext as _
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Account
from apps.api.account_queries import (
    find_traded_account,
)
from apps.api.context import workspace
from apps.api.transaction_projection import (
    _transaction_calculation_row,
)
from apps.market_data.models import (
    Instrument,
)
from apps.transactions.models import Transaction


def _selected_traded_account(request: Request, kind: str) -> Account | None | Response:
    """Validate and resolve an optional native account filter."""

    if "cuenta_id" in request.query_params:
        return Response({"error": _("Use account_id for account filtering")}, status=400)
    value = request.query_params.get("account_id")
    if not value or value == "all":
        return None
    try:
        account_uuid = UUID(value)
    except (TypeError, ValueError):
        return Response({"error": _("A valid account ID was expected")}, status=400)
    account_kind = {
        Instrument.Kind.FUND: Account.Kind.FUNDS,
        Instrument.Kind.STOCK: Account.Kind.STOCKS,
        Instrument.Kind.CRYPTO: Account.Kind.CRYPTO,
    }[Instrument.Kind(kind)]
    return find_traded_account(request, account_kind, account_uuid)


def transaction_queryset(
    request: Request, kind: str, selected_account: Account | None = None
) -> QuerySet[Transaction]:
    queryset = (
        Transaction.objects.select_related("account", "instrument")
        .prefetch_related("instrument__identifiers")
        .filter(account__workspace=workspace(request), instrument__kind=kind)
    )
    if selected_account is not None:
        queryset = queryset.filter(account=selected_account)
    return queryset


def _transaction_calculation_list(
    request: Request, kind: str, selected_account: Account | None = None
) -> list[dict[str, Any]]:
    """Return private legacy-shaped rows for pure position calculations."""
    queryset = transaction_queryset(request, kind, selected_account)
    return [_transaction_calculation_row(item) for item in queryset.order_by("trade_date")]
