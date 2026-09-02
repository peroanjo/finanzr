from __future__ import annotations

from typing import Any

from apps.market_data.models import Instrument


def number(value: Any) -> float:
    return float(value or 0)


def provider_name(obj: Any) -> str:
    return str(obj.provider.name if obj.provider_id else obj.provider_label)


def identifier(instrument: Instrument, scheme: str) -> str:
    result = next((item for item in instrument.identifiers.all() if item.scheme == scheme), None)
    return result.value if result else ""
