from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.imports.legacy import LegacyImportError, LegacyImportReport
from apps.imports.legacy_service import LegacyImportService


class Command(BaseCommand):
    help = "Transactionally import Finanzr legacy CSV files"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--data-dir",
            type=Path,
            default=settings.PROJECT_DIR / "data",
            help="Directory containing the 21 CSV files",
        )
        parser.add_argument("--workspace", required=True, help="Destination workspace slug")
        parser.add_argument("--workspace-name", help="Name used when creating the workspace")
        parser.add_argument(
            "--owner-email",
            help="Initial owner; required when the workspace does not exist yet",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run the full import and roll back the transaction afterwards",
        )
        parser.add_argument(
            "--validate",
            action="store_true",
            help="Fail the import when any reconciliation does not match",
        )
        parser.add_argument("--json", action="store_true", help="Output the report as JSON")

    def handle(self, *args: Any, **options: Any) -> None:
        service = LegacyImportService(
            data_dir=options["data_dir"],
            workspace_slug=options["workspace"],
            workspace_name=options.get("workspace_name"),
            owner_email=options.get("owner_email"),
            dry_run=options["dry_run"],
            validate=options["validate"],
        )
        try:
            report = service.run()
        except LegacyImportError as exc:
            if options["json"]:
                self.stdout.write(
                    json.dumps(service.report.as_dict(), ensure_ascii=False, indent=2)
                )
            raise CommandError(str(exc)) from exc
        if options["json"]:
            self.stdout.write(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        else:
            self._write_report(report)

    def _write_report(self, report: LegacyImportReport) -> None:
        mode = "DRY RUN" if report.dry_run else "IMPORT"
        self.stdout.write(self.style.MIGRATE_HEADING(f"{mode} · workspace {report.workspace}"))
        self.stdout.write("file | read | created | updated | unchanged | skipped | warnings")
        for filename, item in sorted(report.files.items()):
            self.stdout.write(
                f"{filename} | {item.read} | {item.created} | {item.updated} | "
                f"{item.unchanged} | {item.skipped} | {item.warnings}"
            )
        self.stdout.write(self.style.MIGRATE_HEADING("Reconciliation"))
        for check in report.checks:
            marker = "OK" if check.matches else "ERROR"
            line = f"[{marker}] {check.name}"
            if not check.matches:
                line += f" · CSV={check.source!r} SQL={check.database!r}"
            self.stdout.write(line)
        if report.issues:
            self.stdout.write(self.style.WARNING(f"Warnings: {len(report.issues)}"))
            for issue in report.issues:
                location = issue.get("filename") or "general"
                if issue.get("row_number"):
                    location += f":{issue['row_number']}"
                self.stdout.write(f"- {location} [{issue['code']}] {issue['message']}")
        conclusion = "validated" if report.valid else "completed with differences"
        if report.dry_run:
            conclusion += "; no changes were persisted"
        self.stdout.write(self.style.SUCCESS(f"Import {conclusion}."))
