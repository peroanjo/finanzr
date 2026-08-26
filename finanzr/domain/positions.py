"""Proportional cost and P&L for traded positions."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .money import ZERO, as_float, cents, decimal

Record = Mapping[str, Any]


def base_amount(order: Record) -> Decimal:
    """Return the amount normalized to the workspace currency when available."""
    value = order.get("importe_base")
    return decimal(order.get("importe_neto") if value in (None, "") else value)


@dataclass(frozen=True)
class Position:
    asset_id: str
    name: str
    quantity: Decimal
    cost: Decimal
    current_price: Decimal | None
    realized_pnl: Decimal

    @property
    def current_value(self) -> Decimal | None:
        if self.current_price is None:
            return None
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> Decimal | None:
        value = self.current_value
        return None if value is None else value - self.cost

    def as_legacy_dict(self, asset_key: str) -> dict[str, Any]:
        value = self.current_value
        pnl = self.unrealized_pnl
        return {
            asset_key: self.asset_id,
            "nombre": self.name,
            "titulos": as_float(self.quantity),
            "coste_total": as_float(self.cost),
            "precio_actual": None if self.current_price is None else as_float(self.current_price),
            "valor_actual": None if value is None else as_float(value),
            "pnl": None if pnl is None else as_float(pnl),
            "pnl_realizada": as_float(cents(self.realized_pnl)),
        }


def calculate_positions(
    orders: Iterable[Record],
    prices: Mapping[str, Any],
    *,
    asset_key: str,
    name_field: str = "nombre_activo",
) -> list[dict[str, Any]]:
    """Calculate open positions and P&L using proportional average cost."""
    grouped: dict[str, list[Record]] = {}
    for order in orders:
        asset_id = str(order.get(asset_key, ""))
        grouped.setdefault(asset_id, []).append(order)

    results = []
    for asset_id in sorted(grouped):
        asset_orders = grouped[asset_id]
        ordered = sorted(asset_orders, key=lambda row: str(row.get("fecha_operacion", "")))
        quantity = ZERO
        cost = ZERO
        realized = ZERO

        for order in ordered:
            order_quantity = decimal(order.get("titulos"))
            net_amount = base_amount(order)
            if order.get("tipo_operacion") == "Compra":
                quantity += order_quantity
                cost += net_amount
            else:
                if quantity > ZERO:
                    sold_cost = cost * (order_quantity / quantity)
                    realized += net_amount - sold_cost
                    cost -= sold_cost
                quantity -= order_quantity

        quantity = max(ZERO, quantity)
        cost = max(ZERO, cost)
        price = prices.get(asset_id)
        position = Position(
            asset_id=asset_id,
            name=str(ordered[-1].get(name_field, asset_id)),
            quantity=quantity,
            cost=cost,
            current_price=None if price is None else decimal(price),
            realized_pnl=realized,
        )
        row = position.as_legacy_dict(asset_key)
        row["moneda"] = str(ordered[0].get("moneda") or "EUR")
        results.append(row)
    return results
