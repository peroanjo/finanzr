from __future__ import annotations

from typing import Any

from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from rest_framework.request import Request

from apps.api.context import workspace
from apps.api.market_data_projection import instrument_row
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
)


def workspace_instruments(request: Request, kind: str) -> QuerySet[Instrument]:
    current_workspace = workspace(request)
    return (
        Instrument.objects.filter(kind=kind)
        .filter(
            Q(transactions__account__workspace=current_workspace)
            | Q(workspace_links__workspace=current_workspace)
        )
        .prefetch_related("identifiers")
        .distinct()
    )


def workspace_instrument(request: Request, scheme: str, value: str) -> Instrument:
    identity = get_object_or_404(
        InstrumentIdentifier.objects.select_related("instrument"),
        scheme=scheme,
        value=value,
        venue="",
    )
    current_workspace = workspace(request)
    if not (
        identity.instrument.transactions.filter(account__workspace=current_workspace).exists()
        or identity.instrument.workspace_links.filter(workspace=current_workspace).exists()
    ):
        from django.http import Http404

        raise Http404
    return identity.instrument


def instrument_rows(request: Request, kind: str) -> list[dict[str, Any]]:
    return [instrument_row(item) for item in workspace_instruments(request, kind)]
