from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.api.context import workspace
from apps.api.permissions import forbidden_if_readonly
from apps.api.real_estate_projection import real_estate_row
from apps.api.real_estate_queries import real_estate_records
from apps.api.request_data import decimal
from apps.api.schemas import (
    RealEstateRequestSerializer,
    RealEstateUpdateRequestSerializer,
)
from apps.market_data.fx import (
    normalize_currency,
)
from apps.real_estate.models import RealEstateCashFlow, RealEstateInvestment
from apps.real_estate.withholding import effective_withholding_rate


def save_real_estate(item: RealEstateInvestment, data: dict[str, Any]) -> None:
    if "name" in data:
        item.name = str(data["name"]).strip()
    if "platform" in data:
        item.provider = None
        item.provider_label = str(data["platform"]).strip()
    if "status" in data:
        item.status = str(data["status"])
    if "start_date" in data:
        item.start_date = data["start_date"]
    if "maturity_date" in data:
        item.maturity_date = data["maturity_date"]
    if "expected_profit" in data:
        item.expected_profit = data["expected_profit"]
    if "expected_irr_percent" in data:
        item.expected_irr = decimal(data["expected_irr_percent"]) / 100
    if "expected_term_months" in data:
        item.expected_term_months = int(data["expected_term_months"] or 0) or None
    if "origin" in data:
        item.origin = str(data["origin"])
    if "tax_rate" in data:
        item.tax_rate = data["tax_rate"]
    item.currency = normalize_currency(item.workspace.base_currency)
    item.save()
    existing_flows_list = list(item.cash_flows.all())
    existing_contribution = sum(
        (flow.amount for flow in existing_flows_list if flow.flow_type == "contribution"),
        Decimal("0"),
    )
    existing_reinvestment = sum(
        (flow.amount for flow in existing_flows_list if flow.flow_type == "reinvestment"),
        Decimal("0"),
    )
    initial = decimal(
        data.get("initial_capital"), str(existing_contribution + existing_reinvestment)
    )
    new = decimal(
        data.get("new_capital"),
        str(initial if "initial_capital" in data else existing_contribution),
    )
    movements = data.get("movements")
    existing_flows = {str(flow.id): flow for flow in item.cash_flows.all()}
    if not isinstance(movements, list):
        movements = [
            {
                "id": flow.id,
                "flow_type": flow.flow_type,
                "amount": flow.amount,
                "effective_date": flow.effective_date,
                "note": flow.source_note,
            }
            for flow in existing_flows_list
            if flow.flow_type
            in {
                RealEstateCashFlow.FlowType.CAPITAL_RETURN,
                RealEstateCashFlow.FlowType.PROFIT,
            }
        ]
    item.cash_flows.all().delete()
    for flow_type, amount, effective, external in (
        ("contribution", new, item.start_date, True),
        ("reinvestment", max(Decimal(0), initial - new), item.start_date, False),
    ):
        if amount > 0:
            RealEstateCashFlow.objects.create(
                investment=item,
                flow_type=flow_type,
                amount=amount,
                effective_date=effective,
                is_external=external,
            )
    allowed_types = {
        RealEstateCashFlow.FlowType.CAPITAL_RETURN,
        RealEstateCashFlow.FlowType.PROFIT,
    }
    for movement in movements:
        if not isinstance(movement, dict):
            continue
        flow_type = str(movement.get("flow_type", ""))
        if flow_type not in allowed_types:
            raise ValueError(_("An invalid real-estate movement type was received"))
        amount = decimal(movement.get("amount"))
        if amount <= 0:
            continue
        flow_date: date | None = (
            movement.get("effective_date")
            if isinstance(movement.get("effective_date"), date)
            else None
        )
        existing_flow = existing_flows.get(str(movement.get("id") or ""))
        withholding_rate = (
            existing_flow.withholding_rate
            if flow_type == RealEstateCashFlow.FlowType.PROFIT
            and existing_flow is not None
            and existing_flow.flow_type == RealEstateCashFlow.FlowType.PROFIT
            and existing_flow.withholding_rate is not None
            else (
                effective_withholding_rate(item)
                if flow_type == RealEstateCashFlow.FlowType.PROFIT
                else None
            )
        )
        RealEstateCashFlow.objects.create(
            investment=item,
            flow_type=flow_type,
            amount=amount,
            effective_date=flow_date,
            withholding_rate=withholding_rate,
            is_external=False,
            source_note=str(movement.get("note", ""))[:240],
        )


@api_view(["GET", "POST"])
def real_estate(request: Request) -> Response:
    if request.method == "GET":
        return Response(real_estate_records(request))
    if denied := forbidden_if_readonly(request):
        return denied
    serializer = RealEstateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    data = serializer.validated_data
    item = RealEstateInvestment(
        workspace=workspace(request),
        name=str(data["name"]),
        start_date=data["start_date"],
    )
    try:
        with transaction.atomic():
            save_real_estate(item, data)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    item.refresh_from_db()
    return Response(real_estate_row(item), status=201)


@api_view(["PUT", "DELETE"])
def real_estate_detail(request: Request, investment_id: UUID) -> Response:
    if denied := forbidden_if_readonly(request):
        return denied
    item = get_object_or_404(RealEstateInvestment, workspace=workspace(request), pk=investment_id)
    if request.method == "DELETE":
        item.cash_flows.all().delete()
        item.delete()
        return Response({"ok": True})
    serializer = RealEstateUpdateRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=400)
    try:
        with transaction.atomic():
            save_real_estate(item, serializer.validated_data)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    return Response(real_estate_row(item))
