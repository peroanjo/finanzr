from datetime import timedelta
from importlib import import_module

import pytest
from apps.accounts.models import Account
from apps.audit.models import AuditEvent
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceInvitation, WorkspaceMembership
from django.apps import apps as django_apps
from django.contrib import admin as django_admin
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient


def create_member(workspace: Workspace, email: str, role: str = User.Role.USER) -> User:
    user = User.objects.create_user(email=email, password="a-safe-password-2026", role=role)
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=user,
        role=WorkspaceMembership.Role.OWNER
        if role == User.Role.ADMIN
        else WorkspaceMembership.Role.EDITOR,
    )
    return user


@pytest.mark.django_db
def test_only_admin_can_list_and_create_users() -> None:
    workspace = Workspace.objects.create(name="Personal", slug="personal")
    admin = create_member(workspace, "admin@example.com", User.Role.ADMIN)
    regular = create_member(workspace, "regular@example.com")
    client = APIClient()

    client.force_authenticate(regular)
    assert client.get("/api/administration/users").status_code == 403

    client.force_authenticate(admin)
    response = client.post(
        "/api/administration/users",
        {
            "email": "new@example.com",
            "display_name": "Nueva persona",
            "role": "user",
            "password": "another-safe-password-2026",
            "password_confirmation": "another-safe-password-2026",
        },
        format="json",
    )

    assert response.status_code == 201
    created = User.objects.get(email="new@example.com")
    assert created.role == User.Role.USER
    assert created.check_password("another-safe-password-2026")
    created_membership = WorkspaceMembership.objects.select_related("workspace").get(user=created)
    assert created_membership.role == WorkspaceMembership.Role.OWNER
    assert created_membership.workspace != workspace
    assert created_membership.workspace.name == "Nueva persona"
    assert not created_membership.workspace.accounts.exists()
    assert AuditEvent.objects.filter(event_type="user.created", object_id=created.id).exists()
    listed = client.get("/api/administration/users")
    assert listed.status_code == 200
    assert {item["email"] for item in listed.json()} == {
        "admin@example.com",
        "regular@example.com",
        "new@example.com",
    }


@pytest.mark.django_db
def test_administratively_created_user_cannot_read_the_creators_balances() -> None:
    workspace = Workspace.objects.create(name="Creator", slug="creator")
    admin = create_member(workspace, "admin@example.com", User.Role.ADMIN)
    Account.objects.create(
        workspace=workspace,
        name="Creator secret balance",
        kind=Account.Kind.SAVINGS,
        external_id="synthetic:creator-account",
    )
    client = APIClient()
    client.force_authenticate(admin)
    created_response = client.post(
        "/api/administration/users",
        {
            "email": "isolated@example.com",
            "display_name": "Isolated person",
            "role": "user",
            "password": "another-safe-password-2026",
            "password_confirmation": "another-safe-password-2026",
        },
        format="json",
    )
    assert created_response.status_code == 201

    created = User.objects.get(email="isolated@example.com")
    client.force_authenticate(created)
    balances = client.get("/api/savings/accounts")

    assert balances.status_code == 200
    assert balances.json() == []
    assert not WorkspaceMembership.objects.filter(user=created, workspace=workspace).exists()


@pytest.mark.django_db
def test_django_admin_creation_also_provisions_a_personal_workspace() -> None:
    candidate = User(email="django-admin-created@example.com", display_name="Django Admin User")
    candidate.set_password("another-safe-password-2026")
    model_admin = django_admin.site._registry[User]

    model_admin.save_model(RequestFactory().post("/admin/users/user/add/"), candidate, None, False)

    membership = WorkspaceMembership.objects.select_related("workspace").get(user=candidate)
    assert membership.role == WorkspaceMembership.Role.OWNER
    assert membership.workspace.slug == f"personal-{candidate.id.hex}"


@pytest.mark.django_db
def test_data_repair_moves_legacy_admin_created_user_out_of_creators_workspace() -> None:
    creator_workspace = Workspace.objects.create(
        name="Legacy creator", slug="legacy-creator", base_currency="USD"
    )
    creator = create_member(creator_workspace, "legacy-admin@example.com", User.Role.ADMIN)
    affected = User.objects.create_user(
        email="legacy-affected@example.com", password="another-safe-password-2026"
    )
    WorkspaceMembership.objects.create(
        workspace=creator_workspace,
        user=affected,
        role=WorkspaceMembership.Role.EDITOR,
    )
    AuditEvent.objects.create(
        workspace=creator_workspace,
        actor=creator,
        event_type="user.created",
        object_type="user",
        object_id=affected.id,
    )

    migration = import_module("apps.workspaces.migrations.0004_repair_personal_workspaces")
    migration.repair_personal_workspaces(django_apps, None)

    assert not WorkspaceMembership.objects.filter(
        user=affected, workspace=creator_workspace
    ).exists()
    repaired = WorkspaceMembership.objects.select_related("workspace").get(user=affected)
    assert repaired.role == WorkspaceMembership.Role.OWNER
    assert repaired.workspace.base_currency == "USD"


@pytest.mark.django_db
def test_data_repair_preserves_an_explicitly_accepted_workspace_invitation() -> None:
    shared_workspace = Workspace.objects.create(name="Explicitly shared", slug="explicit-share")
    creator = create_member(shared_workspace, "sharing-admin@example.com", User.Role.ADMIN)
    affected = User.objects.create_user(
        email="invited@example.com", password="another-safe-password-2026"
    )
    WorkspaceMembership.objects.create(
        workspace=shared_workspace,
        user=affected,
        role=WorkspaceMembership.Role.EDITOR,
    )
    AuditEvent.objects.create(
        workspace=shared_workspace,
        actor=creator,
        event_type="user.created",
        object_type="user",
        object_id=affected.id,
    )
    WorkspaceInvitation.objects.create(
        workspace=shared_workspace,
        email=affected.email,
        role=WorkspaceMembership.Role.EDITOR,
        token_hash="a" * 64,
        invited_by=creator,
        expires_at=timezone.now() + timedelta(days=1),
        accepted_at=timezone.now(),
    )
    AuditEvent.objects.create(
        workspace=shared_workspace,
        actor=affected,
        event_type="api.post",
        object_type="/api/workspaces/invitations/accept",
        metadata={"status": 200},
    )
    affected.email = "renamed-after-invitation@example.com"
    affected.save(update_fields=("email",))

    migration = import_module("apps.workspaces.migrations.0004_repair_personal_workspaces")
    migration.repair_personal_workspaces(django_apps, None)

    assert WorkspaceMembership.objects.filter(
        user=affected,
        workspace=shared_workspace,
        role=WorkspaceMembership.Role.EDITOR,
    ).exists()
    assert WorkspaceMembership.objects.filter(
        user=affected,
        role=WorkspaceMembership.Role.OWNER,
        workspace__slug=f"personal-{affected.id.hex}",
    ).exists()


@pytest.mark.django_db
def test_admin_can_block_unblock_and_delete_another_user() -> None:
    workspace = Workspace.objects.create(name="Personal", slug="personal")
    admin = create_member(workspace, "admin@example.com", User.Role.ADMIN)
    regular = create_member(workspace, "regular@example.com")
    client = APIClient()
    client.force_authenticate(admin)
    detail_url = f"/api/administration/users/{regular.id}"

    blocked = client.patch(detail_url, {"is_active": False}, format="json")
    assert blocked.status_code == 200
    regular.refresh_from_db()
    assert regular.is_active is False
    login_attempt = APIClient().post(
        "/api/auth/login",
        {"email": regular.email, "password": "a-safe-password-2026"},
        format="json",
    )
    assert login_attempt.status_code == 400

    unblocked = client.patch(detail_url, {"is_active": True}, format="json")
    assert unblocked.status_code == 200
    deleted = client.delete(detail_url)
    assert deleted.status_code == 204
    assert not User.objects.filter(pk=regular.id).exists()
    assert client.delete(f"/api/administration/users/{admin.id}").status_code == 400


@pytest.mark.django_db
def test_admin_can_delete_a_user_with_a_private_personal_workspace() -> None:
    admin_workspace = Workspace.objects.create(name="Administrator", slug="administrator")
    admin = create_member(admin_workspace, "admin@example.com", User.Role.ADMIN)
    client = APIClient()
    client.force_authenticate(admin)
    created_response = client.post(
        "/api/administration/users",
        {
            "email": "deletable@example.com",
            "display_name": "Deletable person",
            "role": "user",
            "password": "another-safe-password-2026",
            "password_confirmation": "another-safe-password-2026",
        },
        format="json",
    )
    created = User.objects.get(id=created_response.json()["id"])
    personal_workspace = Workspace.objects.get(memberships__user=created)

    deleted = client.delete(f"/api/administration/users/{created.id}")

    assert deleted.status_code == 204
    assert not User.objects.filter(pk=created.id).exists()
    personal_workspace.refresh_from_db()
    assert personal_workspace.archived_at is not None


@pytest.mark.django_db
def test_admin_cannot_delete_an_owner_while_other_workspace_members_remain() -> None:
    admin_workspace = Workspace.objects.create(name="Administrator", slug="admin-delete-check")
    admin = create_member(admin_workspace, "admin@example.com", User.Role.ADMIN)
    shared_workspace = Workspace.objects.create(name="Shared", slug="shared-delete-check")
    owner = User.objects.create_user(
        email="owner@example.com", password="another-safe-password-2026"
    )
    WorkspaceMembership.objects.create(
        workspace=shared_workspace,
        user=owner,
        role=WorkspaceMembership.Role.OWNER,
    )
    other_member = User.objects.create_user(
        email="viewer@example.com", password="another-safe-password-2026"
    )
    WorkspaceMembership.objects.create(
        workspace=shared_workspace,
        user=other_member,
        role=WorkspaceMembership.Role.VIEWER,
    )
    client = APIClient()
    client.force_authenticate(admin)

    response = client.delete(f"/api/administration/users/{owner.id}")

    assert response.status_code == 409
    assert User.objects.filter(pk=owner.id).exists()
    shared_workspace.refresh_from_db()
    assert shared_workspace.archived_at is None


@pytest.mark.django_db
def test_admin_can_edit_role_email_name_and_password() -> None:
    workspace = Workspace.objects.create(name="Personal", slug="personal")
    admin = create_member(workspace, "admin@example.com", User.Role.ADMIN)
    regular = create_member(workspace, "regular@example.com")
    client = APIClient()
    client.force_authenticate(admin)

    response = client.patch(
        f"/api/administration/users/{regular.id}",
        {
            "email": "editor@example.com",
            "display_name": "Persona editada",
            "role": "admin",
            "password": "a-renewed-safe-password-2026",
            "password_confirmation": "a-renewed-safe-password-2026",
        },
        format="json",
    )

    assert response.status_code == 200
    regular.refresh_from_db()
    assert regular.email == "editor@example.com"
    assert regular.display_name == "Persona editada"
    assert regular.role == User.Role.ADMIN
    assert regular.check_password("a-renewed-safe-password-2026")
    event = AuditEvent.objects.get(
        event_type="user.updated",
        object_id=regular.id,
    )
    assert "email" in event.metadata["changed_fields"]
