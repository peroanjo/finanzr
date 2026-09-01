"""Investment account rules and monthly performance calculations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

from .money import as_float, cents, decimal


def monthly_pnl(
    history: Iterable[Mapping[str, Any]],
    *,
    account_id: int | str | UUID,
    date: str,
    value: Any,
    contribution: Any,
    explicit_pnl: Any = None,
) -> float:
    """Calculate value change minus contribution for legacy or UUID account IDs."""
    if explicit_pnl not in (None, ""):
        return as_float(decimal(explicit_pnl))
    previous = [
        record
        for record in history
        if str(record.get("cuenta_id") or "") == str(account_id)
        and str(record.get("fecha", "")) < date
    ]
    if not previous:
        return 0.0
    previous_value = decimal(
        max(previous, key=lambda record: str(record.get("fecha", ""))).get("valor")
    )
    result = decimal(value) - previous_value - decimal(contribution)
    return as_float(cents(result))
