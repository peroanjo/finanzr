"""Investment account rules and monthly performance calculations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .money import as_float, cents, decimal


def monthly_pnl(
    history: Iterable[Mapping[str, Any]],
    *,
    account_id: int,
    date: str,
    value: Any,
    contribution: Any,
    explicit_pnl: Any = None,
) -> float:
    """Calculate value change minus contribution unless explicit P&L is provided."""
    if explicit_pnl not in (None, ""):
        return as_float(decimal(explicit_pnl))
    previous = [
        record
        for record in history
        if int(record.get("cuenta_id") or 0) == account_id and str(record.get("fecha", "")) < date
    ]
    if not previous:
        return 0.0
    previous_value = decimal(
        max(previous, key=lambda record: str(record.get("fecha", ""))).get("valor")
    )
    result = decimal(value) - previous_value - decimal(contribution)
    return as_float(cents(result))
