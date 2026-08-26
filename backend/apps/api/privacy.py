from __future__ import annotations

from typing import cast

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.api import views
from apps.api.auth import user_payload
from apps.audit.models import AuditEvent
from apps.users.models import User
from apps.workspaces.models import WorkspaceMembership


def export_payload(request: Request) -> dict[str, object]:
    user = cast(User, request.user)
    return {
        "format": "finanzr-workspace-v1",
        "workspace": user_payload(user, request),
        "summary": views.summary(request).data,
        "savings_accounts": views.savings_accounts(request).data,
        "savings_history": views.savings_history(request).data,
        "investment_accounts": views.investment_accounts(request).data,
        "investment_history": views.investment_history(request).data,
        "portfolio": views.portfolio(request).data,
        "real_estate": views.real_estate(request).data,
        "calculator": views.calculator(request).data,
        "budget": views.budget(request).data,
        "fund_accounts": views.fund_accounts(request).data,
        "stock_accounts": views.stock_accounts(request).data,
        "crypto_accounts": views.crypto_accounts(request).data,
        "funds": views.funds(request).data,
        "stocks": views.stocks(request).data,
        "cryptos": views.cryptos(request).data,
        "orders": views.orders(request).data,
        "stock_orders": views.stock_orders(request).data,
        "crypto_orders": views.crypto_orders(request).data,
        "fund_prices": views.fund_prices(request).data,
        "stock_prices": views.stock_prices(request).data,
        "crypto_prices": views.crypto_prices(request).data,
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
