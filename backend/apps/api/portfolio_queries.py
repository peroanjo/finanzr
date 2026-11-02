from __future__ import annotations

from rest_framework.request import Request

from apps.api.sharing import visible_resources
from apps.portfolio.models import ManualAsset


def _summary_manual_assets(request: Request) -> list[ManualAsset]:
    """Count canonical records once; matching attributes do not prove identity."""
    return list(
        visible_resources(request, ManualAsset)
        .filter(archived_at__isnull=True)
        .select_related("provider")
    )
