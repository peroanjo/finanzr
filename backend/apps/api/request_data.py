from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils.translation import gettext as _
from rest_framework.request import Request


def payload(request: Request) -> dict[str, Any]:
    return request.data if isinstance(request.data, dict) else {}


def decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value not in (None, "") else default))
    except InvalidOperation as exc:
        raise ValueError(_("A valid number was expected")) from exc


def percentage_rate(value: Any) -> Decimal:
    """Parse a withholding rate and enforce the public percentage range."""

    try:
        rate = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(_("A valid percentage between 0 and 100 was expected")) from exc
    if not rate.is_finite() or rate < 0 or rate > 100:
        raise ValueError(_("A valid percentage between 0 and 100 was expected"))
    return rate
