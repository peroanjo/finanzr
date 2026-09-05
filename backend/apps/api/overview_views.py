from __future__ import annotations

from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.api.overview_queries import _overview_calculation


@api_view(["GET"])
def summary(request: Request) -> Response:
    summary_payload, _history = _overview_calculation(request)
    return Response(summary_payload)


@api_view(["GET"])
def net_worth_history(request: Request) -> Response:
    _summary_payload, history = _overview_calculation(request)
    return Response(history)
