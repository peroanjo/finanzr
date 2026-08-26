import pytest
from apps.audit.models import AuditEvent
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
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
    assert WorkspaceMembership.objects.get(user=created).role == WorkspaceMembership.Role.EDITOR
    assert AuditEvent.objects.filter(event_type="user.created", object_id=created.id).exists()
    listed = client.get("/api/administration/users")
    assert listed.status_code == 200
    assert {item["email"] for item in listed.json()} == {
        "admin@example.com",
        "regular@example.com",
        "new@example.com",
    }


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
