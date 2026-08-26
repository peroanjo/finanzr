import pytest
from apps.accounts.models import Account
from apps.api.uploads import instrument as imported_instrument
from apps.audit.models import AuditEvent
from apps.market_data.models import Instrument, InstrumentIdentifier
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from rest_framework.test import APIClient


def member(workspace: Workspace, email: str, role: str) -> User:
    user = User.objects.create_user(email=email, password="a-safe-password")
    WorkspaceMembership.objects.create(workspace=workspace, user=user, role=role)
    return user


@pytest.mark.django_db
def test_session_login_logout_and_workspace_selection() -> None:
    first = Workspace.objects.create(name="Primero", slug="primero")
    second = Workspace.objects.create(name="Segundo", slug="segundo")
    user = member(first, "owner@example.com", "owner")
    WorkspaceMembership.objects.create(workspace=second, user=user, role="viewer")
    client = APIClient(enforce_csrf_checks=True)

    csrf_response = client.get("/api/auth/csrf")
    token = csrf_response.json()["csrfToken"]
    login_response = client.post(
        "/api/auth/login",
        {"email": user.email, "password": "a-safe-password"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert login_response.status_code == 200
    token = login_response.json()["csrfToken"]

    selected = client.put(
        "/api/workspaces/current",
        {"workspace_id": str(second.id)},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert selected.status_code == 200
    assert selected.json()["active_workspace_id"] == str(second.id)
    assert client.post("/api/auth/logout", HTTP_X_CSRFTOKEN=token).status_code == 200
    assert client.get("/api/auth/me").status_code in {401, 403}


@pytest.mark.django_db
def test_login_requires_csrf_token() -> None:
    workspace = Workspace.objects.create(name="CSRF", slug="csrf")
    user = member(workspace, "csrf@example.com", "owner")
    client = APIClient(enforce_csrf_checks=True)

    rejected = client.post(
        "/api/auth/login",
        {"email": user.email, "password": "a-safe-password"},
        format="json",
    )
    assert rejected.status_code == 403

    token = client.get("/api/auth/csrf").json()["csrfToken"]
    accepted = client.post(
        "/api/auth/login",
        {"email": user.email, "password": "a-safe-password"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert accepted.status_code == 200


@pytest.mark.django_db
def test_workspace_data_is_horizontally_isolated() -> None:
    own = Workspace.objects.create(name="Propio", slug="propio")
    foreign = Workspace.objects.create(name="Ajeno", slug="ajeno")
    user = member(own, "owner@example.com", "owner")
    Account.objects.create(
        workspace=own, name="Visible", kind="savings", external_id="legacy:savings:1"
    )
    Account.objects.create(
        workspace=foreign, name="Secreto", kind="savings", external_id="legacy:savings:1"
    )
    client = APIClient()
    client.force_authenticate(user)

    response = client.get("/api/savings/accounts")

    assert response.status_code == 200
    assert [item["nombre"] for item in response.json()] == ["Visible"]


@pytest.mark.django_db
def test_workspace_cannot_mutate_a_shared_instrument_catalog_entry() -> None:
    first = Workspace.objects.create(name="Catalog one", slug="catalog-one")
    second = Workspace.objects.create(name="Catalog two", slug="catalog-two")
    first_user = member(first, "catalog-one@example.com", "owner")
    second_user = member(second, "catalog-two@example.com", "editor")
    client = APIClient()
    client.force_authenticate(first_user)
    created = client.post(
        "/api/stocks",
        {"isin": "US0000000001", "ticker": "CATONE", "nombre": "First name"},
        format="json",
    )
    assert created.status_code == 201

    client.force_authenticate(second_user)
    linked = client.post(
        "/api/stocks",
        {"isin": "US0000000001", "ticker": "CATONE", "nombre": "Second name"},
        format="json",
    )
    assert linked.status_code == 201
    instrument = Instrument.objects.get(
        identifiers__scheme=InstrumentIdentifier.Scheme.ISIN,
        identifiers__value="US0000000001",
    )
    assert instrument.name == "First name"
    assert instrument.quote_currency == "EUR"
    assert instrument.workspace_links.filter(workspace=second).exists()
    assert InstrumentIdentifier.objects.filter(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.YAHOO,
        value="CATONE",
    ).exists()
    assert not InstrumentIdentifier.objects.filter(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.YAHOO,
        value="CATTWO",
    ).exists()

    rejected_update = client.put(
        "/api/stocks/US0000000001",
        {"ticker": "CATTWO", "nombre": "Second name"},
        format="json",
    )
    assert rejected_update.status_code == 409
    imported_instrument(
        {"isin": "US0000000001", "nombre_activo": "Imported name"},
        Instrument.Kind.STOCK,
        "USD",
        second,
    )
    instrument.refresh_from_db()
    assert instrument.name == "First name"
    assert instrument.quote_currency == "EUR"


@pytest.mark.django_db
def test_viewer_cannot_write_and_editor_can() -> None:
    workspace = Workspace.objects.create(name="Equipo", slug="equipo")
    viewer = member(workspace, "viewer@example.com", "viewer")
    editor = member(workspace, "editor@example.com", "editor")
    client = APIClient()
    body = {"nombre": "Cuenta", "banco": "Banco", "tipo": "Corriente"}

    client.force_authenticate(viewer)
    assert client.post("/api/savings/accounts", body, format="json").status_code == 403

    client.force_authenticate(editor)
    response = client.post("/api/savings/accounts", body, format="json")
    assert response.status_code == 201
    assert response["Content-Security-Policy"].startswith("default-src 'self'")
    assert AuditEvent.objects.filter(workspace=workspace, actor=editor).count() == 1


@pytest.mark.django_db
def test_user_can_change_own_email_and_password_but_demo_cannot() -> None:
    workspace = Workspace.objects.create(name="Personal", slug="personal")
    user = member(workspace, "person@example.com", WorkspaceMembership.Role.OWNER)
    client = APIClient()
    client.force_login(user)

    email_response = client.patch(
        "/api/auth/account",
        {
            "display_name": "Nombre actualizado",
            "email": "new@example.com",
            "current_password": "a-safe-password",
        },
        format="json",
    )
    assert email_response.status_code == 200
    assert email_response.json()["email"] == "new@example.com"
    assert email_response.json()["display_name"] == "Nombre actualizado"

    password_response = client.post(
        "/api/auth/password",
        {
            "current_password": "a-safe-password",
            "password": "a-new-safe-password-2026",
            "password_confirmation": "a-new-safe-password-2026",
        },
        format="json",
    )
    assert password_response.status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    user.refresh_from_db()
    assert user.check_password("a-new-safe-password-2026")

    demo = member(workspace, "demo@example.com", WorkspaceMembership.Role.OWNER)
    demo.role = User.Role.DEMO
    demo.save(update_fields=("role",))
    client.force_login(demo)
    blocked = client.patch(
        "/api/auth/account",
        {"email": "changed@example.com", "current_password": "a-safe-password"},
        format="json",
    )
    assert blocked.status_code == 403


@pytest.mark.django_db
def test_invitation_can_only_be_used_by_its_recipient() -> None:
    workspace = Workspace.objects.create(name="Equipo", slug="equipo")
    owner = member(workspace, "owner@example.com", "owner")
    recipient = User.objects.create_user(email="new@example.com", password="a-safe-password")
    attacker = User.objects.create_user(email="attacker@example.com", password="a-safe-password")
    client = APIClient()
    client.force_authenticate(owner)
    created = client.post(
        "/api/workspaces/invitations", {"email": recipient.email, "role": "editor"}, format="json"
    )
    token = created.json()["token"]

    client.force_authenticate(attacker)
    assert (
        client.post(
            "/api/workspaces/invitations/accept", {"token": token}, format="json"
        ).status_code
        == 400
    )

    client.force_authenticate(recipient)
    assert (
        client.post(
            "/api/workspaces/invitations/accept", {"token": token}, format="json"
        ).status_code
        == 200
    )
    assert WorkspaceMembership.objects.get(user=recipient, workspace=workspace).role == "editor"
