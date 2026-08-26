"""Public contract for all Finanzr importers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .i18n import gettext


class InputKind(str, Enum):  # noqa: UP042 - keep the importer API compatible with Python 3.9
    """Input representations accepted by the import system."""

    TEXT = "text"
    RECORDS = "records"


class ImporterError(ValueError):
    """Input error that can be shown to the user without a traceback."""


@dataclass(frozen=True)
class ImporterFormat:
    """File format publicly declared by an importer."""

    extension: str
    label: str
    description: str

    def describe(self) -> dict[str, str]:
        return {
            "extension": self.extension,
            "label": gettext(self.label),
            "description": gettext(self.description),
        }


@dataclass(frozen=True)
class ImporterField:
    """Field expected in the source file."""

    name: str
    label: str
    description: str
    example: str
    required: bool = True
    position: int | None = None

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": gettext(self.label),
            "description": gettext(self.description),
            "example": self.example,
            "required": self.required,
            "position": self.position,
        }


@dataclass(frozen=True)
class ImportContext:
    """Shared external information needed by a parser to normalize rows."""

    account_id: Any
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportIssue:
    """Warning or error found during a partial import."""

    code: str
    message: str
    severity: str = "warning"
    row_number: int | None = None
    value: str | None = None


@dataclass
class ImportResult:
    """Normalized result returned by all importers."""

    records: list[dict[str, Any]] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)
    skipped: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def imported(self) -> int:
        return len(self.records)

    @property
    def warnings(self) -> list[ImportIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def errors(self) -> list[ImportIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]


class BaseImporter(ABC):
    """Minimum interface implemented by every collaborative parser."""

    slug: str
    display_name: str
    target: str
    target_label: str
    description: str
    source_instructions: str
    input_kind: InputKind
    formats: tuple[ImporterFormat, ...] = ()
    fields: tuple[ImporterField, ...] = ()
    rules: tuple[str, ...] = ()

    @property
    def accepted_extensions(self) -> tuple[str, ...]:
        return tuple(item.extension for item in self.formats)

    @property
    def required_fields(self) -> frozenset[str]:
        return frozenset(item.name for item in self.fields if item.required)

    def describe(self) -> dict[str, Any]:
        """Serializable metadata for documentation or a future UI."""
        return {
            "slug": self.slug,
            "display_name": gettext(self.display_name),
            "target": self.target,
            "target_label": gettext(self.target_label),
            "description": gettext(self.description),
            "source_instructions": gettext(self.source_instructions),
            "input_kind": self.input_kind.value,
            "accepted_extensions": list(self.accepted_extensions),
            "required_fields": sorted(self.required_fields),
            "formats": [item.describe() for item in self.formats],
            "fields": [item.describe() for item in self.fields],
            "rules": [gettext(rule) for rule in self.rules],
        }

    def parse(self, source: Any, context: ImportContext) -> ImportResult:
        """Validate the input shape and delegate concrete normalization."""
        prepared = self._prepare_source(source)
        return self._parse(prepared, context)

    def _prepare_source(self, source: Any) -> Any:
        if self.input_kind == InputKind.TEXT:
            if not isinstance(source, str):
                raise ImporterError(gettext("%(slug)s requires text input") % {"slug": self.slug})
            return source

        if isinstance(source, (str, bytes, Mapping)) or not isinstance(source, Iterable):
            raise ImporterError(
                gettext("%(slug)s requires a sequence of records") % {"slug": self.slug}
            )
        records = list(source)
        if any(not isinstance(record, Mapping) for record in records):
            raise ImporterError(
                gettext("%(slug)s received a row that is not a record") % {"slug": self.slug}
            )
        if self.required_fields:
            for row_number, record in enumerate(records, start=1):
                missing = self.required_fields - set(record)
                if missing:
                    fields = ", ".join(sorted(missing))
                    raise ImporterError(
                        gettext("Required columns are missing from row %(row_number)s: %(fields)s")
                        % {"row_number": row_number, "fields": fields}
                    )
        return records

    @abstractmethod
    def _parse(self, source: Any, context: ImportContext) -> ImportResult:
        """Transform validated input into normalized records."""
