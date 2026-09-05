from __future__ import annotations

from typing import Any

from rest_framework.request import Request

from apps.api.context import workspace
from apps.api.real_estate_projection import real_estate_row
from apps.common.models import InstallationSettings
from apps.real_estate.models import RealEstateInvestment


def real_estate_records(request: Request) -> list[dict[str, Any]]:
    items = (
        RealEstateInvestment.objects.filter(workspace=workspace(request), archived_at__isnull=True)
        .prefetch_related("cash_flows", "provider")
        .order_by("-start_date", "name", "id")
    )
    default_tax_rate = InstallationSettings.load().default_crowdfunding_tax_rate
    return [real_estate_row(item, default_tax_rate=default_tax_rate) for item in items]
