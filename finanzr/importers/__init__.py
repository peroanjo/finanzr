"""Finanzr public importer API and registry."""

from .base import (
    BaseImporter,
    ImportContext,
    ImporterError,
    ImporterField,
    ImporterFormat,
    ImportIssue,
    ImportResult,
    InputKind,
)
from .funds import IMPORTER as FUND_BROKER_IMPORTER
from .kraken import IMPORTER as KRAKEN_SPOT_IMPORTER
from .registry import ImporterRegistry
from .trade_republic import IMPORTER as TRADE_REPUBLIC_IMPORTER

importers = ImporterRegistry()
importers.register(FUND_BROKER_IMPORTER)
importers.register(KRAKEN_SPOT_IMPORTER)
importers.register(TRADE_REPUBLIC_IMPORTER)


__all__ = [
    "BaseImporter",
    "ImportContext",
    "ImporterError",
    "ImporterField",
    "ImporterFormat",
    "ImportIssue",
    "ImportResult",
    "InputKind",
    "ImporterRegistry",
    "importers",
]
