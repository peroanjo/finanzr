"""Canonical native projection for manual portfolio assets."""

from __future__ import annotations

from typing import Any

from apps.api.legacy import number, provider_name
from apps.portfolio.models import ManualAsset


def manual_asset_row(item: ManualAsset) -> dict[str, Any]:
    """Return the public native shape for one persisted manual asset."""

    return {
        "id": str(item.id),
        "name": item.name,
        "asset_class": item.asset_class,
        "subtype": item.subtype,
        "platform": provider_name(item),
        "value": number(item.value),
        "currency": item.currency,
    }
