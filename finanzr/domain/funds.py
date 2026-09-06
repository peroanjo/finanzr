"""Open fund position calculations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any
from uuid import UUID

from .money import ZERO, decimal
from .positions import base_amount

BUY_TYPES = {"SUSCRIPCION", "SUSCR.POR TRASPASO I"}
SELL_TYPES = {"REEMB.POR TRASPASO I", "REEMBOLSO"}
REALIZED_BUY_TYPES = BUY_TYPES | {"buy", "transfer_in"}
REALIZED_SELL_TYPES = SELL_TYPES | {"sell", "transfer_out"}


def _realized_amount(order: Mapping[str, Any]) -> Decimal:
    if "importe_base" in order or "importe_neto" in order:
        return base_amount(order)
    base_value = order.get("base_net_amount")
    return decimal(order.get("net_amount") if base_value in (None, "") else base_value)


def calculate_fund_realized_pnl(orders: Iterable[Mapping[str, Any]]) -> Decimal:
    """Calculate realized fund P&L using the established aggregate policy.

    Orders are grouped by ISIN, regardless of chronological lot sequence. Buy
    and transfer-in quantities form one aggregate cost, while sell and
    transfer-out quantities form one aggregate sale value. The result is the
    sale value less the proportional average cost of all acquired units.
    """
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for order in orders:
        isin = str(order.get("isin", ""))
        grouped.setdefault(isin, []).append(order)

    total = ZERO
    for asset_orders in grouped.values():
        bought_quantity = ZERO
        buy_cost = ZERO
        sold_quantity = ZERO
        sale_value = ZERO
        for order in asset_orders:
            operation = str(order.get("tipo_operacion") or order.get("operation_type") or "")
            raw_quantity = order["titulos"] if "titulos" in order else order.get("quantity")
            quantity = decimal(raw_quantity)
            amount = _realized_amount(order)
            if operation in REALIZED_BUY_TYPES:
                bought_quantity += quantity
                buy_cost += amount
            elif operation in REALIZED_SELL_TYPES:
                sold_quantity += quantity
                sale_value += amount
        if bought_quantity > ZERO and sold_quantity > ZERO:
            total += sale_value - (buy_cost / bought_quantity) * sold_quantity
    return total


def calculate_fund_positions(
    orders: Iterable[Mapping[str, Any]],
    funds: Mapping[str, Mapping[str, Any]],
    prices: Mapping[str, Any],
    *,
    account_id: int | str | UUID | None = None,
) -> list[dict[str, Any]]:
    """Calculate live fund cost and P&L, excluding closed positions."""
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for order in orders:
        if account_id is not None and str(order.get("cuenta_id") or "") != str(account_id):
            continue
        isin = str(order.get("isin", ""))
        grouped.setdefault(isin, []).append(order)

    result = []
    for isin, asset_orders in grouped.items():
        buys = [order for order in asset_orders if order.get("tipo_operacion") in BUY_TYPES]
        sells = [order for order in asset_orders if order.get("tipo_operacion") in SELL_TYPES]
        total_bought = sum((decimal(order.get("titulos")) for order in buys), ZERO)
        total_sold = sum((decimal(order.get("titulos")) for order in sells), ZERO)
        net_quantity = total_bought - total_sold
        if net_quantity <= decimal("0.0001"):
            continue

        total_invested = sum((base_amount(order) for order in buys), ZERO)
        average_buy_price = total_invested / total_bought if total_bought > ZERO else ZERO
        net_invested = total_invested - average_buy_price * total_sold
        average_price = net_invested / net_quantity if net_quantity > ZERO else ZERO

        raw_price = prices.get(isin)
        current_price = None if raw_price in (None, "") else decimal(raw_price)
        current_value = None if current_price is None else current_price * net_quantity
        pnl = None if current_value is None else current_value - net_invested
        pnl_pct = None if pnl is None or net_invested <= ZERO else pnl / net_invested

        fund = funds.get(isin, {})
        result.append(
            {
                "isin": isin,
                "nombre": fund.get("nombre", isin),
                "tipo": fund.get("tipo", ""),
                "subtipo": fund.get("subtipo", ""),
                "total_invertido": round(float(net_invested), 2),
                "participaciones": round(float(net_quantity), 6),
                "precio_medio": round(float(average_price), 4),
                "precio_actual": None if current_price is None else round(float(current_price), 4),
                "valor_actual": None if current_value is None else round(float(current_value), 2),
                "pnl": None if pnl is None else round(float(pnl), 2),
                "pnl_pct": None if pnl_pct is None else round(float(pnl_pct), 4),
                "moneda": str(fund.get("moneda") or "EUR"),
            }
        )
    return result
