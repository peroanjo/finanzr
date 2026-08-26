"""Explicit registry of available importers."""

from __future__ import annotations

from typing import Any

from .base import BaseImporter, ImportContext, ImportResult


class ImporterRegistry:
    def __init__(self) -> None:
        self._importers: dict[str, BaseImporter] = {}

    def register(self, importer: BaseImporter) -> None:
        if not all(
            (
                importer.slug,
                importer.display_name,
                importer.target,
                importer.target_label,
                importer.description,
                importer.source_instructions,
            )
        ):
            raise ValueError("Every importer requires a public identity and description")
        if not importer.formats or not importer.fields:
            raise ValueError("Every importer must declare formats and expected fields")
        if len(importer.accepted_extensions) != len(set(importer.accepted_extensions)):
            raise ValueError(f"Duplicate extensions in {importer.slug}")
        field_names = [field.name for field in importer.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError(f"Duplicate fields in {importer.slug}")
        if importer.slug in self._importers:
            raise ValueError(f"Duplicate importer: {importer.slug}")
        self._importers[importer.slug] = importer

    def get(self, slug: str) -> BaseImporter:
        try:
            return self._importers[slug]
        except KeyError as exc:
            raise KeyError(f"Unregistered importer: {slug}") from exc

    def all(self) -> tuple[BaseImporter, ...]:
        return tuple(self._importers[slug] for slug in sorted(self._importers))

    def catalog(self) -> list[dict[str, Any]]:
        return [importer.describe() for importer in self.all()]

    def parse(self, slug: str, source: Any, context: ImportContext) -> ImportResult:
        return self.get(slug).parse(source, context)
