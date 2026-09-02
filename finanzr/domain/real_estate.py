"""Real-estate capital rules independent from web frameworks and pandas."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .money import ZERO, as_float, decimal, is_missing

Record = Mapping[str, Any]


def live_capital(project: Record) -> float:
    """Capital currently remaining invested in a project."""
    initial = project.get("initial_capital")
    if not is_missing(initial):
        return as_float(decimal(initial) - decimal(project.get("returned_capital")))
    return 0.0


def new_capital(project: Record) -> float:
    """External money contributed, excluding reinvested capital."""
    value = project.get("new_capital")
    if not is_missing(value):
        return as_float(decimal(value))
    initial = project.get("initial_capital")
    if not is_missing(initial):
        return as_float(decimal(initial))
    return 0.0


def live_capital_for_month(project: Record, month: str) -> float:
    """Live capital in YYYY-MM without applying returns retroactively."""
    start = str(project.get("start_date") or "")[:7]
    if not start or month < start:
        return 0.0

    movements = project.get("movements")
    if isinstance(movements, list):
        returned = sum(
            (
                decimal(movement.get("amount"))
                for movement in movements
                if isinstance(movement, Mapping)
                and movement.get("flow_type") == "capital_return"
                and str(movement.get("effective_date") or "")[:7] <= month
            ),
            ZERO,
        )
        return as_float(max(ZERO, decimal(project.get("initial_capital")) - returned))

    current = decimal(live_capital(project))
    returned = decimal(project.get("returned_capital"))
    return_month = str(project.get("return_date") or "")[:7]
    if returned and return_month and month < return_month:
        current += returned
    return as_float(current)
