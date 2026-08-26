"""Open fund position calculations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .money import ZERO, decimal
from .positions import base_amount

BUY_TYPES = {"SUSCRIPCION", "SUSCR.POR TRASPASO I"}
SELL_TYPES = {"REEMB.POR TRASPASO I", "REEMBOLSO"}


def calculate_fund_positions(
    orders: Iterable[Mapping[str, Any]],
    funds: Mapping[str, Mapping[str, Any]],
    prices: Mapping[str, Any],
    *,
    account_id: int | None = None,
) -> list[dict[str, Any]]:
    """Calculate live fund cost and P&L, excluding closed positions."""
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for order in orders:
        if account_id is not None and int(order.get("cuenta_id") or 0) != account_id:
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
