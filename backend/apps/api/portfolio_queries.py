from __future__ import annotations

from typing import Any

from rest_framework.request import Request

from apps.api.context import workspace
from apps.api.projection import number, provider_name
from apps.portfolio.models import ManualAsset
from finanzr.domain.real_estate import live_capital


def _normalized_match_text(value: Any) -> str:
    return " ".join(str(value or "").casefold().replace("-", " ").split())


def _manual_asset_is_real_estate_duplicate(
    item: ManualAsset, properties: list[dict[str, Any]]
) -> bool:
    """Exclude only a manual row proven to mirror a real-estate project.

    Asset class labels are user-controlled and are not evidence of a
    duplicate.  Correlation therefore requires the canonical project name
    and current value to match (and, when both are available, its provider).
    This keeps legitimate manually entered property-like assets visible.
    """

    item_name = _normalized_match_text(item.name)
    item_provider = _normalized_match_text(provider_name(item))
    item_value = number(item.value)
    for project in properties:
        if item_name != _normalized_match_text(project.get("name")):
            continue
        project_provider = _normalized_match_text(project.get("platform"))
        if item_provider and project_provider and item_provider != project_provider:
            continue
        if abs(item_value - number(live_capital(project))) <= 0.01:
            return True
    return False


def _summary_manual_assets(request: Request, properties: list[dict[str, Any]]) -> list[ManualAsset]:
    return [
        item
        for item in ManualAsset.objects.filter(
            workspace=workspace(request), archived_at__isnull=True
        ).select_related("provider")
        if not _manual_asset_is_real_estate_duplicate(item, properties)
    ]
