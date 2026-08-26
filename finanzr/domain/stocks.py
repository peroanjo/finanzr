"""Stock-specific rules and confirmed split handling."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .money import decimal
from .positions import calculate_positions

Record = Mapping[str, Any]


def apply_splits(orders: Iterable[Record], splits: Iterable[Record]) -> list[dict[str, Any]]:
    """Adjust orders preceding each split without changing their total cost."""
    adjusted = [dict(order) for order in orders]
    for split in splits:
        try:
            ratio = decimal(split.get("ratio"))
        except (ArithmeticError, ValueError):
            continue
        if ratio <= 0:
            continue
        isin = split.get("isin")
        split_date = str(split.get("fecha") or "")[:10]
        for order in adjusted:
            if order.get("isin") == isin and str(order.get("fecha_operacion", "")) < split_date:
                order["titulos"] = float(decimal(order.get("titulos")) * ratio)
                order["precio_compra"] = float(decimal(order.get("precio_compra")) / ratio)
    return adjusted


def calculate_stock_positions(
    orders: Iterable[Record], prices: Mapping[str, Any], splits: Iterable[Record]
) -> list[dict[str, Any]]:
    return calculate_positions(apply_splits(orders, splits), prices, asset_key="isin")
