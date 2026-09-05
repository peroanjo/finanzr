from __future__ import annotations

from typing import Any, cast

from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.api.budget_queries import budget_rows
from apps.api.context import workspace
from apps.api.permissions import forbidden_if_readonly
from apps.api.request_data import decimal
from apps.market_data.fx import (
    normalize_currency,
)
from apps.planning.models import BudgetLine


@api_view(["GET", "PUT"])
def budget(request: Request) -> Response:
    current_workspace = workspace(request)
    items = BudgetLine.objects.filter(workspace=current_workspace)
    if request.method == "PUT":
        if denied := forbidden_if_readonly(request):
            return denied
        submitted_rows = cast(list[dict[str, Any]], request.data)
        with transaction.atomic():
            items.delete()
            BudgetLine.objects.bulk_create(
                [
                    BudgetLine(
                        workspace=current_workspace,
                        category=str(row["categoria"]),
                        amount=decimal(row["cantidad"]),
                        currency=normalize_currency(current_workspace.base_currency),
                        line_type=str(row["tipo"]),
                        sort_order=index,
                    )
                    for index, row in enumerate(submitted_rows)
                ]
            )
    return Response(budget_rows(request))
