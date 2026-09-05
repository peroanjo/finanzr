from typing import Any

from rest_framework.request import Request

from apps.api.context import workspace
from apps.api.projection import number
from apps.planning.models import BudgetLine


def budget_rows(request: Request) -> list[dict[str, Any]]:
    items = BudgetLine.objects.filter(workspace=workspace(request))
    return [
        {
            "categoria": x.category,
            "cantidad": number(x.amount),
            "tipo": x.line_type,
            "moneda": x.currency,
        }
        for x in items
    ]
