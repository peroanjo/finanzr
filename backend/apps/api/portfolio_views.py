from __future__ import annotations

from datetime import date
from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.api.account_queries import (
    resolve_provider,
)
from apps.api.context import workspace
from apps.api.permissions import forbidden_if_readonly
from apps.api.portfolio_projection import manual_asset_row
from apps.api.request_data import payload
from apps.api.schemas import (
    ManualAssetRequestSerializer,
    ManualAssetUpdateRequestSerializer,
)
from apps.market_data.fx import (
    normalize_currency,
)
from apps.portfolio.models import ManualAsset


@api_view(["GET", "POST"])
def portfolio(request: Request) -> Response:
    current_workspace = workspace(request)
    items = ManualAsset.objects.filter(
        workspace=current_workspace, archived_at__isnull=True
    ).select_related("provider")
    if request.method == "POST":
        if denied := forbidden_if_readonly(request):
            return denied
        serializer = ManualAssetRequestSerializer(data=payload(request))
        if not serializer.is_valid():
            return Response({"error": serializer.errors}, status=400)
        data = serializer.validated_data
        provider, provider_label = resolve_provider(str(data.get("platform", "")))
        item = ManualAsset.objects.create(
            workspace=current_workspace,
            name=data["name"].strip(),
            asset_class=data["asset_class"].strip(),
            subtype=str(data.get("subtype", "")).strip(),
            provider=provider,
            provider_label=provider_label,
            value=data["value"],
            currency=normalize_currency(current_workspace.base_currency),
            valued_at=date.today(),
        )
        return Response(manual_asset_row(item), status=201)
    return Response([manual_asset_row(item) for item in items.order_by("name", "id")])


@api_view(["PUT", "DELETE"])
def portfolio_detail(request: Request, asset_id: UUID) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    item = get_object_or_404(ManualAsset, workspace=workspace(request), pk=asset_id)
    if request.method == "DELETE":
        item.delete()
        return Response({"ok": True})
    serializer = ManualAssetUpdateRequestSerializer(data=payload(request))
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    if "name" in data:
        item.name = data["name"].strip()
    if "asset_class" in data:
        item.asset_class = data["asset_class"].strip()
    if "subtype" in data:
        item.subtype = data["subtype"].strip()
    if "platform" in data:
        item.provider, item.provider_label = resolve_provider(str(data["platform"]))
    if "value" in data:
        item.value = data["value"]
    item.save()
    return Response(manual_asset_row(item))
