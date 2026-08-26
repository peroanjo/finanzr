"""Shared helpers for exact monetary calculations."""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

ZERO = Decimal("0")
CENT = Decimal("0.01")


def is_missing(value: Any) -> bool:
    """Recognize empty and NaN values coming from external data adapters."""
    return value is None or value == "" or (isinstance(value, float) and math.isnan(value))


def decimal(value: Any, default: Decimal = ZERO) -> Decimal:
    """Convert input values to Decimal without an intermediate float approximation."""
    if is_missing(value):
        return default
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def cents(value: Decimal) -> Decimal:
    """Round using the standard financial ROUND_HALF_UP rule."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def as_float(value: Decimal) -> float:
    """Convert to the JSON output type used by API clients."""
    return float(value)
