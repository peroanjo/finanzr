from io import StringIO

import pytest
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
def test_bootstrap_owner_is_idempotent() -> None:
    call_command(
        "bootstrap_owner",
        email="owner@example.test",
        password="a-safe-password-2026",
        workspace="household",
        workspace_name="Household",
    )
    call_command(
        "bootstrap_owner",
        email="owner@example.test",
        password="a-different-password",
        workspace="household",
        workspace_name="Ignored on rerun",
    )

    assert User.objects.filter(email="owner@example.test").count() == 1
    user = User.objects.get(email="owner@example.test")
    assert user.check_password("a-safe-password-2026")
    workspace = Workspace.objects.get(slug="household")
    assert WorkspaceMembership.objects.filter(
        user=user, workspace=workspace, role=WorkspaceMembership.Role.OWNER
    ).exists()


@pytest.mark.django_db
def test_bootstrap_owner_accepts_password_from_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", StringIO("stdin-password\n"))
    call_command(
        "bootstrap_owner",
        email="stdin@example.test",
        password_stdin=True,
        workspace="stdin-space",
    )
    assert User.objects.get(email="stdin@example.test").check_password("stdin-password")


@pytest.mark.django_db
def test_bootstrap_owner_rejects_two_password_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", StringIO("stdin-password\n"))
    with pytest.raises(CommandError, match="either --password or --password-stdin"):
        call_command(
            "bootstrap_owner",
            email="stdin@example.test",
            password="argument-password",
            password_stdin=True,
        )


@pytest.mark.django_db
def test_bootstrap_owner_reconciles_an_existing_user_without_resetting_password() -> None:
    user = User.objects.create_user(
        email="owner@example.test", password="existing-safe-password-2026"
    )

    call_command(
        "bootstrap_owner",
        email="OWNER@example.test",
        password="ignored-safe-password-2026",
        workspace="household",
        workspace_name="Household",
    )

    user.refresh_from_db()
    assert user.role == User.Role.ADMIN
    assert user.check_password("existing-safe-password-2026")
    assert WorkspaceMembership.objects.filter(
        user=user,
        workspace__slug="household",
        role=WorkspaceMembership.Role.OWNER,
    ).exists()
