from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command

from apps.common.backups import encrypt_backup


class Command(BaseCommand):
    help = "Create an encrypted logical database backup"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("output", type=Path)

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.EXTERNAL_CREDENTIALS_KEY:
            raise CommandError("Configure EXTERNAL_CREDENTIALS_KEY")
        output: Path = options["output"]
        if output.exists():
            raise CommandError("The destination file already exists")
        stream = StringIO()
        call_command(
            "dumpdata",
            "common",
            "users",
            "workspaces",
            "accounts",
            "market_data",
            "imports",
            "transactions",
            "real_estate",
            "portfolio",
            "planning",
            "audit",
            natural_foreign=True,
            natural_primary=True,
            stdout=stream,
        )
        output.write_bytes(
            encrypt_backup(stream.getvalue().encode(), settings.EXTERNAL_CREDENTIALS_KEY)
        )
        self.stdout.write(self.style.SUCCESS(f"Encrypted backup created: {output}"))
