import json
from pathlib import Path

import pytest
from apps.accounts.credentials import CredentialCipher
from apps.common.backups import decrypt_backup, encrypt_backup
from apps.common.models import InstallationSettings, SummaryPreference
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings


def test_encrypted_backup_roundtrip_and_wrong_key_rejected() -> None:
    key = Fernet.generate_key().decode()
    encrypted = encrypt_backup(b'{"financial":"private"}', key)

    assert b"private" not in encrypted
    assert decrypt_backup(encrypted, key) == b'{"financial":"private"}'

    wrong_key = Fernet.generate_key().decode()
    try:
        decrypt_backup(encrypted, wrong_key)
    except ValueError as exc:
        assert str(exc) == "Corrupted backup or incorrect key"
    else:
        raise AssertionError("An incorrect key must not decrypt the backup")


@override_settings(EXTERNAL_CREDENTIALS_KEY=Fernet.generate_key().decode())
def test_external_credentials_are_encrypted_at_rest() -> None:
    cipher = CredentialCipher()
    encrypted = cipher.encrypt("broker-secret")

    assert b"broker-secret" not in encrypted
    assert cipher.decrypt(encrypted) == "broker-secret"


@pytest.mark.django_db(transaction=True)
@override_settings(EXTERNAL_CREDENTIALS_KEY=Fernet.generate_key().decode())
def test_backup_restore_includes_installation_and_summary_preferences(tmp_path: Path) -> None:
    installation = InstallationSettings.load()
    installation.default_summary_sources = ["savings"]
    installation.save(update_fields=("default_summary_sources", "updated_at"))
    workspace = Workspace.objects.create(name="Backup", slug="backup")
    user = User.objects.create_user(email="backup@example.test", password="safe-password")
    WorkspaceMembership.objects.create(workspace=workspace, user=user, role="owner")
    preference = SummaryPreference.objects.create(
        user=user,
        workspace=workspace,
        included_sources=["stocks"],
    )

    destination = tmp_path / "backup.json.fernet"
    call_command("backup_database", destination)
    payload = json.loads(
        decrypt_backup(destination.read_bytes(), settings.EXTERNAL_CREDENTIALS_KEY)
    )
    assert {item["model"] for item in payload} >= {
        "common.installationsettings",
        "common.summarypreference",
    }

    preference_id = preference.pk
    call_command("flush", interactive=False, verbosity=0)
    call_command("restore_database", destination, "--confirm-empty-database")
    assert InstallationSettings.load().default_summary_sources == ["savings"]
    assert SummaryPreference.objects.filter(pk=preference_id).exists()
