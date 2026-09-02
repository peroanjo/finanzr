from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts.models import Account, AccountSnapshot
from apps.api import views
from apps.api.auth import user_payload
from apps.api.investment_projection import investment_account_row, investment_snapshot_row
from apps.api.legacy import account_row
from apps.api.portfolio_projection import manual_asset_row
from apps.api.savings_projection import savings_account_row, savings_snapshot_row
from apps.audit.models import AuditEvent
from apps.portfolio.models import ManualAsset
from apps.users.models import User
from apps.workspaces.models import WorkspaceMembership


def _view_data(view: Callable[[Any], Any], request: Request) -> object:
    """Call a decorated API view with its underlying Django request."""

    raw_request = getattr(request, "_request", request)
    return view(raw_request).data


def _native_savings_sections(
    request: Request,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Serialize every savings row for the workspace export's v2 contract."""

    accounts = list(
        Account.objects.filter(
            workspace=views.workspace(request),
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
            workspace=views.workspace(request),
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
    """Serialize every manual asset so the v2 export is complete."""

    assets = ManualAsset.objects.filter(workspace=views.workspace(request)).select_related(
        "provider"
    )
    return [manual_asset_row(asset) for asset in assets.order_by("name", "id")]


def _native_traded_accounts(request: Request, kind: str) -> list[dict[str, object]]:
    """Export every traded account, including archived and legacy-origin rows."""

    accounts = (
        Account.objects.filter(workspace=views.workspace(request), kind=kind)
        .select_related("provider")
        .order_by("name", "id")
    )
    return [account_row(account) for account in accounts]


def export_payload(request: Request) -> dict[str, object]:
    user = cast(User, request.user)
    savings_accounts, savings_history = _native_savings_sections(request)
    investment_accounts, investment_history = _native_investment_sections(request)
    return {
        # v2 is a document-level cutover for native account and asset sections;
        # traded orders retain their transitional response envelope.
        "format": "finanzr-workspace-v2",
        "workspace": user_payload(user, request),
        "summary": views._overview_calculation(request)[0],
        "savings_accounts": savings_accounts,
        "savings_history": savings_history,
        "investment_accounts": investment_accounts,
        "investment_history": investment_history,
        "portfolio": _native_portfolio_section(request),
        "real_estate": _view_data(views.real_estate, request),
        "budget": _view_data(views.budget, request),
        "fund_accounts": _native_traded_accounts(request, Account.Kind.FUNDS),
        "stock_accounts": _native_traded_accounts(request, Account.Kind.STOCKS),
        "crypto_accounts": _native_traded_accounts(request, Account.Kind.CRYPTO),
        "funds": _view_data(views.funds, request),
        "stocks": _view_data(views.stocks, request),
        "cryptos": _view_data(views.cryptos, request),
        "orders": _view_data(views.orders, request),
        "stock_orders": _view_data(views.stock_orders, request),
        "crypto_orders": _view_data(views.crypto_orders, request),
        "fund_prices": _view_data(views.fund_prices, request),
        "stock_prices": _view_data(views.stock_prices, request),
        "crypto_prices": _view_data(views.crypto_prices, request),
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
    membership = views.active_membership(request)
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
