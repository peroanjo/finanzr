"""Crypto-asset position rules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .positions import calculate_positions


def calculate_crypto_positions(
    orders: Iterable[Mapping[str, Any]], prices: Mapping[str, Any]
) -> list[dict[str, Any]]:
    return calculate_positions(orders, prices, asset_key="symbol")
