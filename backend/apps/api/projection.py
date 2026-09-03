from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from apps.market_data.models import Instrument, InstrumentIdentifier


def number(value: Any) -> float:
    return float(value or 0)


def provider_name(obj: Any) -> str:
    return str(obj.provider.name if obj.provider_id else obj.provider_label)


def select_identifier(
    identifiers: Iterable[InstrumentIdentifier], scheme: str
) -> InstrumentIdentifier | None:
    """Select one stable identifier for a textual market-data projection.

    Canonical identities are always the required default-venue row; their
    primary flags do not change importer resolution. Provider identifiers
    prefer the primary row, then the default venue, then stable value/venue
    ordering.
    """
    candidates = [item for item in identifiers if item.scheme == scheme]
    if scheme in {InstrumentIdentifier.Scheme.ISIN, InstrumentIdentifier.Scheme.CRYPTO_SYMBOL}:
        candidates = [item for item in candidates if item.venue == ""]
        candidates.sort(key=lambda item: (item.value, item.venue, str(item.id)))
    else:
        candidates.sort(
            key=lambda item: (
                not item.is_primary,
                item.venue != "",
                item.value,
                item.venue,
                str(item.id),
            )
        )
    return candidates[0] if candidates else None


def identifier(instrument: Instrument, scheme: str) -> str:
    result = select_identifier(instrument.identifiers.all(), scheme)
    return result.value if result else ""
