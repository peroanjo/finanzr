"""Compatibility wrapper for the shared investment performance engine."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .investment_performance import calculate_investment_performance


def calculate_account_performance(
    orders: Iterable[Mapping[str, Any]],
    prices: Mapping[str, Mapping[str, Any]],
    *,
    account_id: int | str,
) -> list[dict[str, Any]]:
    """Calculate fund performance without counting internal transfers as money."""
    return calculate_investment_performance(
        orders,
        prices,
        kind="fund",
        account_id=account_id,
    )
