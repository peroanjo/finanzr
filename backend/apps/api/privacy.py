from __future__ import annotations

from typing import cast

from django.db import transaction
from django.http import Http404
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Account, AccountSnapshot
from apps.api.account_projection import account_row
from apps.api.auth import user_payload
from apps.api.budget_queries import budget_rows
from apps.api.context import active_membership, workspace
from apps.api.instrument_queries import instrument_rows
from apps.api.investment_projection import investment_account_row, investment_snapshot_row
from apps.api.market_queries import price_rows
from apps.api.overview_queries import _overview_calculation
from apps.api.portfolio_projection import manual_asset_row
from apps.api.real_estate_queries import real_estate_records
from apps.api.savings_projection import savings_account_row, savings_snapshot_row
from apps.api.transaction_queries import selected_traded_account, transaction_rows
from apps.audit.models import AuditEvent
from apps.market_data.fx import CurrencyConversionError
from apps.portfolio.models import ManualAsset
from apps.users.models import User
from apps.workspaces.models import WorkspaceMembership


def _native_savings_sections(
    request: Request,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Serialize every savings row for the workspace export's v4 contract."""

    accounts = list(
        Account.objects.filter(
            workspace=workspace(request),
            kind=Account.Kind.SAVINGS,
        )
        .select_related("provider")
        .order_by("name")
    )
    snapshots = AccountSnapshot.objects.select_related("account").filter(account__in=accounts)
    return (
        [savings_account_row(account) for account in accounts],
        [savings_snapshot_row(snapshot) for snapshot in snapshots.order_by("date")],
    )


def _native_investment_sections(
    request: Request,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Serialize every manual investment row for the workspace export."""

    accounts = list(
        Account.objects.filter(
            workspace=workspace(request),
            kind=Account.Kind.MANUAL_INVESTMENT,
        )
        .select_related("provider")
        .order_by("name")
    )
    snapshots = AccountSnapshot.objects.select_related("account", "account__workspace").filter(
        account__in=accounts
    )
    return (
        [investment_account_row(account) for account in accounts],
        [investment_snapshot_row(snapshot) for snapshot in snapshots.order_by("date")],
    )


def _native_portfolio_section(request: Request) -> list[dict[str, object]]:
    """Serialize every manual asset so the v4 export is complete."""

    assets = ManualAsset.objects.filter(workspace=workspace(request)).select_related("provider")
    return [manual_asset_row(asset) for asset in assets.order_by("name", "id")]


def _native_traded_accounts(request: Request, kind: str) -> list[dict[str, object]]:
    """Export every traded account, including archived and legacy-origin rows."""

    accounts = (
        Account.objects.filter(workspace=workspace(request), kind=kind)
        .select_related("provider")
        .order_by("name", "id")
    )
    return [account_row(account) for account in accounts]


def _export_transaction_rows(request: Request, kind: str) -> object:
    """Preserve v4's request filters and per-section account errors."""
    try:
        selected_account = selected_traded_account(request, kind)
    except ValueError as exc:
        return {"error": str(exc)}
    except Http404 as exc:
        return {"detail": str(exc)}
    return transaction_rows(request, kind, selected_account)


def _export_price_rows(request: Request, kind: str) -> object:
    """Keep unavailable conversions as section errors in the v4 export."""
    try:
        return price_rows(request, kind)
    except CurrencyConversionError as exc:
        return {"error": str(exc)}


def export_payload(request: Request) -> dict[str, object]:
    user = cast(User, request.user)
    savings_accounts, savings_history = _native_savings_sections(request)
    investment_accounts, investment_history = _native_investment_sections(request)
    return {
        # v4 records native transaction HTTP DTOs, native instrument UUID/identifier
        # projections, and native market-price contracts.
        "format": "finanzr-workspace-v4",
        "workspace": user_payload(user, request),
        "summary": _overview_calculation(request)[0],
        "savings_accounts": savings_accounts,
        "savings_history": savings_history,
        "investment_accounts": investment_accounts,
        "investment_history": investment_history,
        "portfolio": _native_portfolio_section(request),
        "real_estate": real_estate_records(request),
        "budget": budget_rows(request),
        "fund_accounts": _native_traded_accounts(request, Account.Kind.FUNDS),
        "stock_accounts": _native_traded_accounts(request, Account.Kind.STOCKS),
        "crypto_accounts": _native_traded_accounts(request, Account.Kind.CRYPTO),
        "funds": instrument_rows(request, "fund"),
        "stocks": instrument_rows(request, "stock"),
        "cryptos": instrument_rows(request, "crypto"),
        "orders": _export_transaction_rows(request, "fund"),
        "stock_orders": _export_transaction_rows(request, "stock"),
        "crypto_orders": _export_transaction_rows(request, "crypto"),
        "fund_prices": _export_price_rows(request, "fund"),
        "stock_prices": _export_price_rows(request, "stock"),
        "crypto_prices": _export_price_rows(request, "crypto"),
    }


@api_view(["GET"])
def export_account(request: Request) -> Response:
    return Response(
        export_payload(request),
        headers={"Content-Disposition": 'attachment; filename="finanzr-export.json"'},
    )


@api_view(["DELETE"])
def delete_account(request: Request) -> Response:
    user = cast(User, request.user)
    if not user.check_password(str(request.data.get("password", ""))):
        return Response({"error": _("Incorrect password")}, status=400)
    memberships = list(WorkspaceMembership.objects.filter(user=user))
    if any(
        item.role == WorkspaceMembership.Role.OWNER
        and item.workspace.memberships.exclude(user=user).exists()
        for item in memberships
    ):
        return Response(
            {"error": _("Transfer ownership of your workspaces before deleting the account")},
            status=409,
        )
    with transaction.atomic():
        for item in memberships:
            if item.role == WorkspaceMembership.Role.OWNER:
                item.workspace.archived_at = timezone.now()
                item.workspace.save(update_fields=("archived_at",))
        user.delete()
    return Response(status=204)


@api_view(["GET"])
def audit_events(request: Request) -> Response:
    membership = active_membership(request)
    if membership.role != WorkspaceMembership.Role.OWNER:
        return Response({"error": _("Insufficient permissions")}, status=403)
    events = AuditEvent.objects.filter(workspace=membership.workspace)[:200]
    return Response(
        [
            {
                "event_type": event.event_type,
                "object_type": event.object_type,
                "status": event.metadata.get("status"),
                "created_at": event.created_at,
            }
            for event in events
        ]
    )
