"""Real-estate capital rules independent from web frameworks and pandas."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .money import ZERO, as_float, decimal, is_missing

Record = Mapping[str, Any]


def live_capital(project: Record) -> float:
    """Capital currently remaining invested in a project."""
    initial = project.get("capital_inicial")
    if not is_missing(initial):
        return as_float(decimal(initial) - decimal(project.get("capital_devuelto")))
    return as_float(decimal(project.get("invertido")))


def total_live_capital(projects: Iterable[Record]) -> float:
    return as_float(sum((decimal(live_capital(project)) for project in projects), ZERO))


def new_capital(project: Record) -> float:
    """External money contributed, excluding reinvested capital."""
    value = project.get("capital_nuevo")
    if not is_missing(value):
        return as_float(decimal(value))
    initial = project.get("capital_inicial")
    if not is_missing(initial):
        return as_float(decimal(initial))
    return as_float(decimal(project.get("invertido")))


def live_capital_for_month(project: Record, month: str) -> float:
    """Live capital in YYYY-MM without applying returns retroactively."""
    start = str(project.get("fecha_inicio") or "")[:7]
    if not start or month < start:
        return 0.0

    movements = project.get("movimientos")
    if isinstance(movements, list):
        returned = sum(
            (
                decimal(movement.get("importe"))
                for movement in movements
                if isinstance(movement, Mapping)
                and movement.get("tipo") == "capital_return"
                and str(movement.get("fecha") or "")[:7] <= month
            ),
            ZERO,
        )
        return as_float(max(ZERO, decimal(project.get("capital_inicial")) - returned))

    current = decimal(live_capital(project))
    returned = decimal(project.get("capital_devuelto"))
    return_month = str(project.get("fecha_devolucion") or "")[:7]
    if returned and return_month and month < return_month:
        current += returned
    return as_float(current)
