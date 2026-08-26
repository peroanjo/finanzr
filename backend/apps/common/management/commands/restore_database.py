from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command

from apps.common.backups import decrypt_backup


class Command(BaseCommand):
    help = "Restore an encrypted logical backup; requires an empty database"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("backup", type=Path)
        parser.add_argument("--confirm-empty-database", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        if not options["confirm_empty_database"]:
            raise CommandError("Add --confirm-empty-database after verifying the destination")
        if not settings.EXTERNAL_CREDENTIALS_KEY:
            raise CommandError("Configure EXTERNAL_CREDENTIALS_KEY")
        source: Path = options["backup"]
        if not source.is_file():
            raise CommandError("The backup does not exist")
        cleartext = decrypt_backup(source.read_bytes(), settings.EXTERNAL_CREDENTIALS_KEY)
        with tempfile.NamedTemporaryFile(suffix=".json") as fixture:
            fixture.write(cleartext)
            fixture.flush()
            call_command("loaddata", fixture.name)
        self.stdout.write(self.style.SUCCESS("Backup restored"))
