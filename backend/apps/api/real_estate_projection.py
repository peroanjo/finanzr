from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.accounts.models import FinancialProvider
from apps.common.models import InstallationSettings
from apps.real_estate.models import RealEstateCashFlow, RealEstateInvestment
from apps.real_estate.withholding import effective_withholding_rate, net_profit


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _platform(item: RealEstateInvestment) -> str:
    provider: FinancialProvider | None = item.provider
    return provider.name if provider else item.provider_label


def _amount(item: RealEstateInvestment, flow_type: str) -> Decimal:
    return sum(
        (flow.amount for flow in item.cash_flows.all() if flow.flow_type == flow_type),
        Decimal("0"),
    )


def real_estate_row(
    item: RealEstateInvestment,
    *,
    default_tax_rate: Decimal | None = None,
) -> dict[str, Any]:
    contribution = _amount(item, RealEstateCashFlow.FlowType.CONTRIBUTION)
    reinvestment = _amount(item, RealEstateCashFlow.FlowType.REINVESTMENT)
    returned = _amount(item, RealEstateCashFlow.FlowType.CAPITAL_RETURN)
    profit = _amount(item, RealEstateCashFlow.FlowType.PROFIT)
    effective_rate = effective_withholding_rate(
        item,
        default_tax_rate
        if default_tax_rate is not None
        else InstallationSettings.load().default_crowdfunding_tax_rate,
    )
    dated_flows = sorted(
        (
            flow
            for flow in item.cash_flows.all()
            if flow.flow_type
            in {
                RealEstateCashFlow.FlowType.CAPITAL_RETURN,
                RealEstateCashFlow.FlowType.PROFIT,
            }
        ),
        key=lambda flow: (flow.effective_date or date.min, flow.created_at),
    )
    return_flows = [
        flow for flow in dated_flows if flow.flow_type == RealEstateCashFlow.FlowType.CAPITAL_RETURN
    ]
    net_realized_profit = sum(
        (
            net_profit(
                flow.amount,
                flow.withholding_rate if flow.withholding_rate is not None else effective_rate,
            )
            for flow in dated_flows
            if flow.flow_type == RealEstateCashFlow.FlowType.PROFIT
        ),
        Decimal("0"),
    )
    estimated_profit = (
        item.expected_profit
        if item.expected_profit is not None
        else max(Decimal("0"), contribution + reinvestment - returned)
        * (item.expected_irr or Decimal("0"))
        * (item.expected_term_months or 0)
        / Decimal("12")
    )
    return {
        "id": str(item.id),
        "name": item.name,
        "platform": _platform(item),
        "status": item.status,
        "initial_capital": _number(contribution + reinvestment),
        "new_capital": _number(contribution),
        "returned_capital": _number(returned),
        "realized_profit": _number(profit),
        "net_realized_profit": _number(net_realized_profit),
        "expected_profit": _number(item.expected_profit)
        if item.expected_profit is not None
        else None,
        "net_expected_profit": _number(net_profit(estimated_profit, effective_rate)),
        "expected_irr_percent": _number(item.expected_irr) * 100,
        "expected_term_months": item.expected_term_months or 0,
        "start_date": item.start_date.isoformat(),
        "maturity_date": item.maturity_date.isoformat() if item.maturity_date else None,
        "return_date": (
            return_flows[-1].effective_date.isoformat()
            if return_flows and return_flows[-1].effective_date
            else None
        ),
        "movements": [
            {
                "id": str(flow.id),
                "flow_type": flow.flow_type,
                "effective_date": flow.effective_date.isoformat() if flow.effective_date else None,
                "amount": _number(flow.amount),
                "note": flow.source_note,
                "applied_tax_rate": (
                    _number(
                        flow.withholding_rate
                        if flow.withholding_rate is not None
                        else effective_rate
                    )
                    if flow.flow_type == RealEstateCashFlow.FlowType.PROFIT
                    else None
                ),
            }
            for flow in dated_flows
        ],
        "origin": item.origin,
        "tax_rate": _number(item.tax_rate) if item.tax_rate is not None else None,
        "currency": item.currency,
    }
