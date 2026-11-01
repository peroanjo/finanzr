"""Central resource visibility and effective permissions for shared workspaces."""

from __future__ import annotations

from uuid import UUID

from django.db.models import Q, QuerySet
from django.utils.translation import gettext as _
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request

from apps.accounts.models import Account
from apps.api.context import active_membership, workspace
from apps.market_data.models import StockSplit, WorkspaceFxOverride, WorkspaceMarketPriceOverride
from apps.portfolio.models import ManualAsset
from apps.real_estate.models import RealEstateInvestment
from apps.workspaces.models import AssetShare, Workspace


def visible_resources[Resource: (Account, ManualAsset, RealEstateInvestment)](
    request: Request, model: type[Resource]
) -> QuerySet[Resource]:
    current = workspace(request)
    # Currency equality is checked on granting and again on reading, protecting
    # historical base amounts even if a workspace is subsequently reconfigured.
    return model.objects.filter(
        Q(workspace=current)
        | Q(
            shares__target=current,
            workspace__archived_at__isnull=True,
            workspace__base_currency=current.base_currency,
        )
    ).distinct()


def visible_accounts(request: Request) -> QuerySet[Account]:
    return visible_resources(request, Account)


def require_resource_write(
    request: Request,
    item: Account | ManualAsset | RealEstateInvestment,
    *,
    delete_resource: bool = False,
) -> None:
    membership = active_membership(request)
    if membership.role == "viewer":
        raise PermissionDenied()
    if item.workspace_id == membership.workspace_id:
        return
    field = {Account: "account", ManualAsset: "manual_asset", RealEstateInvestment: "real_estate"}[
        type(item)
    ]
    if (
        delete_resource
        or not AssetShare.objects.filter(
            target=membership.workspace, access=AssetShare.Access.EDIT, **{field: item}
        ).exists()
    ):
        raise PermissionDenied()


def instrument_sources(request: Request, instrument_id: UUID | str | None) -> list[Workspace]:
    """Return only owners of visible accounts containing this instrument."""
    if instrument_id is None:
        return []
    owner_ids = (
        visible_accounts(request)
        .filter(transactions__instrument_id=instrument_id)
        .values_list("workspace_id", flat=True)
    )
    return list(Workspace.objects.filter(pk__in=owner_ids).order_by("pk"))


def market_scope(
    request: Request, instrument_id: UUID | str | None, *, write: bool = False
) -> Workspace:
    """Keep manual quotes and corporate actions in their original workspace."""
    current = workspace(request)
    if instrument_id is None:
        return current
    owners = instrument_sources(request, instrument_id)
    if not owners:
        return current
    if len(owners) > 1:
        signatures = []
        for owner in owners:
            signatures.append(
                (
                    tuple(
                        StockSplit.objects.filter(workspace=owner, instrument_id=instrument_id)
                        .order_by("effective_date")
                        .values_list("effective_date", "ratio")
                    ),
                    tuple(
                        WorkspaceMarketPriceOverride.objects.filter(
                            workspace=owner, instrument_id=instrument_id
                        ).values_list("quoted_at", "close", "currency")
                    ),
                    tuple(
                        WorkspaceFxOverride.objects.filter(workspace=owner)
                        .order_by("quote_currency", "base_currency", "rate_date")
                        .values_list("quote_currency", "base_currency", "rate_date", "rate")
                    ),
                )
            )
        if len(set(signatures)) > 1:
            raise ValidationError({"error": _("Shared accounts have conflicting market settings")})
    selected = next((owner for owner in owners if owner.pk == current.pk), owners[0])
    if write and (len(owners) > 1 or selected.pk != current.pk):
        # A record grant does not authorize changes to workspace-wide settings
        # that can also affect other, unshared accounts owned by the source.
        raise PermissionDenied()
    return selected


def visible_market_rows[Row: (StockSplit, WorkspaceMarketPriceOverride)](
    request: Request, model: type[Row]
) -> QuerySet[Row]:
    """Apply each visible instrument's canonical market context exactly once."""
    current = workspace(request)
    ids = list(
        visible_accounts(request)
        .filter(transactions__isnull=False)
        .values_list("transactions__instrument_id", flat=True)
        .distinct()
    )
    condition = Q(workspace=current) & ~Q(instrument_id__in=ids)
    for instrument_id in ids:
        scope = market_scope(request, instrument_id)
        condition |= Q(workspace=scope, instrument_id=instrument_id)
    return model.objects.filter(condition)
