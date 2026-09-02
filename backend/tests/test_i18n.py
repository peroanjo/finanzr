import hashlib
from decimal import Decimal

import pytest
from apps.accounts.models import Account
from apps.common.i18n import normalize_language
from apps.common.models import InstallationSettings
from apps.imports.models import ImportBatch
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from django.apps import apps
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import translation
from rest_framework.test import APIClient

from finanzr.importers import ImportContext, ImporterError, importers

VALID_FUND_ROW = (
    "<tr><td>2026-01-02</td><td>2026-01-04</td><td>op-1</td><td>Mercado</td>"
    "<td>SUSCRIPCION</td><td>ES0000000001</td><td>Fondo Demo</td>"
    "<td>12,5</td><td>EUR</td><td>10,25</td><td>128,13</td></tr>"
)


def create_member(*, role: str = User.Role.USER, language: str = "") -> User:
    workspace = Workspace.objects.create(
        name="Personal", slug=f"personal-{role}-{language or 'auto'}"
    )
    user = User.objects.create_user(
        email=f"{role}-{language or 'auto'}@example.com",
        password="a-safe-password-2026",
        role=role,
        language=language,
    )
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=user,
        role=WorkspaceMembership.Role.OWNER,
    )
    return user


def test_normalized_language_is_a_plain_header_safe_string() -> None:
    language = normalize_language("en-GB")

    assert language == "en"
    assert type(language) is str


def test_model_and_admin_labels_use_english_source_and_spanish_catalog() -> None:
    with translation.override("en"):
        assert str(User.Role.ADMIN.label) == "Administrator"
        assert str(User._meta.get_field("display_name").verbose_name) == "display name"
        assert str(apps.get_app_config("accounts").verbose_name) == "Accounts"

    with translation.override("es"):
        assert str(User.Role.ADMIN.label) == "Administrador"
        assert str(User._meta.get_field("display_name").verbose_name) == "nombre visible"
        assert str(apps.get_app_config("accounts").verbose_name) == "Cuentas"


@pytest.mark.django_db
def test_public_installation_preferences_and_accept_language() -> None:
    client = APIClient()

    preferences = client.get("/api/installation/preferences")
    invalid_login = client.post(
        "/api/auth/login",
        {"email": "missing@example.com", "password": "incorrect"},
        format="json",
        HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9",
    )

    assert preferences.status_code == 200
    assert preferences.json() == {
        "default_language": "es-ES",
        "default_crowdfunding_tax_rate": 19.0,
    }
    assert invalid_login.status_code == 400
    assert invalid_login.json()["error"] == "Incorrect email or password"
    assert invalid_login["Content-Language"] == "en"


@pytest.mark.django_db
def test_user_can_override_and_inherit_installation_language() -> None:
    user = create_member()
    client = APIClient()
    client.force_login(user)

    initial = client.get("/api/auth/me")
    selected = client.patch("/api/auth/preferences", {"language": "en"}, format="json")
    inherited = client.patch("/api/auth/preferences", {"language": None}, format="json")

    assert initial.json()["language"] == "es-ES"
    assert initial.json()["preferred_language"] is None
    assert initial.json()["default_language"] == "es-ES"
    assert initial.json()["default_crowdfunding_tax_rate"] == 19.0
    assert selected.status_code == 200
    assert selected.json()["language"] == "en"
    assert selected.json()["preferred_language"] == "en"
    assert selected["Content-Language"] == "en"
    assert inherited.json()["language"] == "es-ES"
    assert inherited.json()["preferred_language"] is None


@pytest.mark.django_db
def test_installation_language_requires_admin_and_updates_inheriting_users() -> None:
    regular = create_member()
    admin = create_member(role=User.Role.ADMIN)
    client = APIClient()
    client.force_login(regular)

    denied = client.patch(
        "/api/installation/preferences", {"default_language": "en"}, format="json"
    )
    client.force_login(admin)
    updated = client.patch(
        "/api/installation/preferences",
        {"default_language": "en", "default_crowdfunding_tax_rate": 21.5},
        format="json",
    )
    me = client.get("/api/auth/me")

    assert denied.status_code == 403
    assert updated.status_code == 200
    assert updated.json() == {
        "default_language": "en",
        "default_crowdfunding_tax_rate": 21.5,
        "language": "en",
    }
    assert InstallationSettings.load().default_language == "en"
    assert InstallationSettings.load().default_crowdfunding_tax_rate == Decimal("21.50")
    assert me.json()["language"] == "en"
    assert me.json()["preferred_language"] is None
    assert me.json()["default_crowdfunding_tax_rate"] == 21.5


@pytest.mark.django_db
def test_installation_tax_rate_rejects_invalid_values() -> None:
    admin = create_member(role=User.Role.ADMIN)
    client = APIClient()
    client.force_login(admin)

    for value in (-0.1, 100.1, "invalid", "NaN"):
        response = client.patch(
            "/api/installation/preferences",
            {"default_crowdfunding_tax_rate": value},
            format="json",
        )
        assert response.status_code == 400
        assert "entre 0 y 100" in response.json()["error"]

    assert InstallationSettings.load().default_crowdfunding_tax_rate == Decimal("19.00")


@pytest.mark.django_db
def test_invalid_personal_language_is_rejected() -> None:
    user = create_member()
    client = APIClient()
    client.force_login(user)

    response = client.patch("/api/auth/preferences", {"language": "fr"}, format="json")

    assert response.status_code == 400
    assert response.json()["error"] == "El idioma no es válido"


@pytest.mark.django_db
def test_password_reset_email_uses_recipient_language() -> None:
    user = create_member(language=User.Language.ENGLISH)
    client = APIClient()

    response = client.post("/api/auth/password-reset", {"email": user.email}, format="json")

    assert response.status_code == 200
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Reset your Finanzr password"
    assert "Use this link to reset it:" in mail.outbox[0].body


@pytest.mark.django_db
def test_financial_validation_error_uses_user_language() -> None:
    user = create_member(language=User.Language.ENGLISH)
    client = APIClient()
    client.force_login(user)

    response = client.get("/api/investment-performance/fund?start=2026-01-01")

    assert response.status_code == 400
    assert response.json()["error"] == "You must provide both a start and an end date"


@pytest.mark.django_db
def test_import_validation_error_uses_user_language() -> None:
    user = create_member(language=User.Language.ENGLISH)
    client = APIClient()
    client.force_login(user)

    response = client.post("/api/fund-orders/upload", {})

    assert response.status_code == 400
    assert response.json()["error"] == "A file and an account are required"


@pytest.mark.django_db
def test_non_inversis_csv_encoding_error_keeps_existing_message_without_batch() -> None:
    user = create_member()
    client = APIClient()
    client.force_login(user)
    account = Account.objects.create(
        workspace=user.memberships.get().workspace,
        name="Synthetic crypto",
        kind=Account.Kind.CRYPTO,
        external_id="legacy:crypto:1",
    )
    content = (
        "txid,pair,time,type,price,cost,fee,vol\n"
        "bad-Á,BTC/EUR,2026-01-01 10:00:00,buy,100,100,1,1\n"
    ).encode("cp1252")

    response = client.post(
        "/api/crypto-orders/upload-kraken-pro",
        {
            "account_id": str(account.id),
            "file": SimpleUploadedFile("trades.csv", content, content_type="text/csv"),
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "El archivo debe estar codificado como UTF-8"
    assert account.import_batches.count() == 0
    assert account.transactions.count() == 0


@pytest.mark.django_db
def test_privacy_validation_error_uses_user_language() -> None:
    user = create_member(language=User.Language.ENGLISH)
    client = APIClient()
    client.force_login(user)

    response = client.delete("/api/account", {"password": "wrong"}, format="json")

    assert response.status_code == 400
    assert response.json()["error"] == "Incorrect password"


@pytest.mark.django_db
def test_api_validation_errors_use_spanish_catalog_by_default() -> None:
    user = create_member()
    client = APIClient()
    client.force_login(user)

    financial = client.get("/api/investment-performance/fund?start=2026-01-01")
    imported = client.post("/api/fund-orders/upload", {})
    privacy = client.delete("/api/account", {"password": "wrong"}, format="json")

    assert financial.json()["error"] == "Debes indicar fecha inicial y final"
    assert imported.json()["error"] == "Falta archivo o cuenta"
    assert privacy.json()["error"] == "Contraseña incorrecta"


@pytest.mark.django_db
def test_importer_catalog_and_parser_messages_use_active_language() -> None:
    user = create_member(language=User.Language.ENGLISH)
    client = APIClient()
    client.force_login(user)

    catalog = client.get("/api/importers")

    assert catalog.status_code == 200
    fund = next(item for item in catalog.json() if item["slug"] == "fund_broker")
    assert fund["target_label"] == "Funds"
    assert fund["fields"][0]["label"] == "Trade date"
    assert fund["rules"][0] == "Rows must keep the exact 11-column order shown."

    with translation.override("en"):
        with pytest.raises(ImporterError, match="Required columns are missing from row 1"):
            importers.parse("kraken_spot", [{"txid": "incomplete"}], ImportContext(account_id=1))


@pytest.mark.django_db
def test_importer_catalog_and_parser_messages_use_spanish_catalog() -> None:
    user = create_member()
    client = APIClient()
    client.force_login(user)

    catalog = client.get("/api/importers")

    assert catalog.status_code == 200
    fund = next(item for item in catalog.json() if item["slug"] == "fund_broker")
    assert fund["target_label"] == "Fondos"
    assert fund["fields"][0]["label"] == "Fecha de operación"
    assert fund["rules"][0] == (
        "Las filas deben conservar exactamente el orden de 11 columnas indicado."
    )

    with translation.override("es"):
        with pytest.raises(ImporterError, match="Faltan columnas obligatorias en la fila 1"):
            importers.parse("kraken_spot", [{"txid": "incomplete"}], ImportContext(account_id=1))


@pytest.mark.django_db
def test_importer_partial_issue_is_stored_in_user_language() -> None:
    user = create_member(language=User.Language.ENGLISH)
    client = APIClient()
    client.force_login(user)
    account = Account.objects.create(
        workspace=user.memberships.get().workspace,
        name="Funds",
        kind=Account.Kind.FUNDS,
        external_id="legacy:funds:1",
    )
    content = SimpleUploadedFile(
        "funds.csv",
        b"not;a;valid;fund;row\n",
        content_type="text/csv",
    )

    assert account.external_id is not None
    response = client.post(
        "/api/fund-orders/upload",
        {"account_id": str(account.id), "file": content},
    )

    assert response.status_code == 200
    assert response.json()["skipped"] == 1
    issue = account.import_batches.get().issues.get()
    assert issue.message == "The row does not contain the expected 11 columns or has invalid values"


@pytest.mark.django_db
def test_inversis_html_upload_decodes_windows_1252_before_parsing() -> None:
    user = create_member(language=User.Language.ENGLISH)
    client = APIClient()
    client.force_login(user)
    account = Account.objects.create(
        workspace=user.memberships.get().workspace,
        name="Synthetic funds",
        kind=Account.Kind.FUNDS,
        external_id="legacy:funds:1",
    )
    html = """
    <table><tr>
      <td>2026-01-02</td><td>2026-01-04</td><td>cp1252-op</td><td>Mercado</td>
      <td>SUSCRIPCION</td><td>ES0000000001</td><td>Fondo Á Demo</td>
      <td>12,5</td><td>EUR</td><td>10,25</td><td>128,13</td>
    </tr></table>
    """

    response = client.post(
        "/api/fund-orders/upload",
        {
            "account_id": str(account.id),
            "file": SimpleUploadedFile("inversis.xls", html.encode("cp1252")),
        },
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert account.import_batches.count() == 1
    assert account.transactions.get().instrument.name == "Fondo Á Demo"


@pytest.mark.django_db
def test_inversis_html_selects_sibling_data_table_and_round_trips_entities() -> None:
    user = create_member(language=User.Language.ENGLISH)
    client = APIClient()
    client.force_login(user)
    account = Account.objects.create(
        workspace=user.memberships.get().workspace,
        name="Synthetic funds",
        kind=Account.Kind.FUNDS,
        external_id="legacy:funds:1",
    )
    source = (
        "<table><tr><td>layout only</td></tr></table>"
        "<table>" + VALID_FUND_ROW.replace("Fondo Demo", "Fondo &amp; Demo") + "</table>"
        "<table>"
        + VALID_FUND_ROW.replace("op-1", "outside-op").replace("Fondo Demo", "Outside")
        + "</table>"
    )

    response = client.post(
        "/api/fund-orders/upload",
        {
            "account_id": str(account.id),
            "file": SimpleUploadedFile("sibling.html", source.encode("utf-8")),
        },
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert account.transactions.count() == 1
    transaction = account.transactions.get()
    assert transaction.external_id == "op-1"
    assert transaction.instrument.name == "Fondo & Demo"


@pytest.mark.django_db
def test_inversis_html_preserves_empty_cell_positions() -> None:
    user = create_member(language=User.Language.ENGLISH)
    client = APIClient()
    client.force_login(user)
    account = Account.objects.create(
        workspace=user.memberships.get().workspace,
        name="Synthetic funds",
        kind=Account.Kind.FUNDS,
        external_id="legacy:funds:1",
    )
    source = "<table>" + VALID_FUND_ROW.replace("<td>Mercado</td>", "<td></td>") + "</table>"

    response = client.post(
        "/api/fund-orders/upload",
        {
            "account_id": str(account.id),
            "file": SimpleUploadedFile("empty-market.html", source.encode("utf-8")),
        },
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1
    transaction = account.transactions.get()
    assert transaction.market == ""
    assert transaction.provider_operation_type == "SUSCRIPCION"


@pytest.mark.django_db
def test_inversis_html_accepts_balanced_table_sections() -> None:
    user = create_member(language=User.Language.ENGLISH)
    client = APIClient()
    client.force_login(user)
    account = Account.objects.create(
        workspace=user.memberships.get().workspace,
        name="Synthetic funds",
        kind=Account.Kind.FUNDS,
        external_id="legacy:funds:1",
    )
    header = (
        "<tr><th>Trade date</th><th>Settlement</th><th>Identifier</th><th>Market</th>"
        "<th>Type</th><th>ISIN</th><th>Fund name</th><th>Units</th><th>Currency</th>"
        "<th>Price</th><th>Amount</th></tr>"
    )
    source = "<table><thead>" + header + "</thead><tbody>" + VALID_FUND_ROW + "</tbody></table>"

    response = client.post(
        "/api/fund-orders/upload",
        {
            "account_id": str(account.id),
            "file": SimpleUploadedFile("sections.html", source.encode("utf-8")),
        },
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert account.transactions.get().external_id == "op-1"


@pytest.mark.parametrize(
    ("filename", "source"),
    (
        ("malformed.xls", "<table><tr><td>open only"),
        ("disjoint.html", "<table></table><tr><td>outside the table</td></tr>"),
        (
            "external-row.xls",
            "<table><tr><td>layout only</td></tr></table>"
            "<tr><td>2026-01-02</td><td>2026-01-04</td><td>op-1</td><td>Mercado</td>"
            "<td>SUSCRIPCION</td><td>ES0000000001</td><td>Fondo Demo</td>"
            "<td>12,5</td><td>EUR</td><td>10,25</td><td>128,13</td></tr>",
        ),
        (
            "unsupported-row.xls",
            "<table>"
            + VALID_FUND_ROW.replace("SUSCRIPCION", "GARBAGE").replace(
                "ES0000000001", "NOT-AN-ISIN"
            )
            + "</table>",
        ),
        (
            "mixed-invalid-row.xls",
            "<table>"
            + VALID_FUND_ROW
            + VALID_FUND_ROW.replace("op-1", "bad-op").replace("SUSCRIPCION", "GARBAGE")
            + "</table>",
        ),
        (
            "mixed-alphabetic-date.xls",
            "<table>"
            + VALID_FUND_ROW
            + VALID_FUND_ROW.replace("2026-01-02", "not-a-date")
            + "</table>",
        ),
        (
            "mixed-empty-date.xls",
            "<table>"
            + VALID_FUND_ROW
            + VALID_FUND_ROW.replace("<td>2026-01-02</td>", "<td></td>")
            + "</table>",
        ),
        (
            "mixed-ten-cell-row.xls",
            "<table>" + VALID_FUND_ROW + VALID_FUND_ROW.replace("<td>128,13</td>", "") + "</table>",
        ),
        (
            "mixed-twelve-cell-row.xls",
            "<table>"
            + VALID_FUND_ROW.replace("</tr>", "<td>extra</td></tr>")
            + VALID_FUND_ROW
            + "</table>",
        ),
        (
            "mixed-direct-text-row.xls",
            "<table>" + VALID_FUND_ROW + "<tr>arbitrary content</tr></table>",
        ),
        (
            "invalid-date.xls",
            "<table>" + VALID_FUND_ROW.replace("2026-01-02", "2026-99-99") + "</table>",
        ),
        (
            "nonfinite.xls",
            "<table>" + VALID_FUND_ROW.replace("12,5", "NaN") + "</table>",
        ),
        (
            "nested-unclosed.xls",
            "<table><tr><td>layout only<table><tr>"
            "<td>2026-01-02</td><td>2026-01-04</td><td>op-1</td><td>Mercado</td>"
            "<td>SUSCRIPCION</td><td>ES0000000001</td><td>Fondo Demo</td>"
            "<td>12,5</td><td>EUR</td><td>10,25</td><td>128,13</td>"
            "</tr></table>",
        ),
        ("one-cell.html", "<table><tr><td>arbitrary content</td></tr></table>"),
        ("stray-row-before.html", VALID_FUND_ROW + "<table>" + VALID_FUND_ROW + "</table>"),
        ("unmatched-close.html", "</table><table>" + VALID_FUND_ROW + "</table>"),
        ("stray-cell-after.html", "<table>" + VALID_FUND_ROW + "</table><td>stray</td>"),
        ("stray-thead-before.html", "<thead></thead><table>" + VALID_FUND_ROW + "</table>"),
        ("unmatched-tbody.html", "</tbody><table>" + VALID_FUND_ROW + "</table>"),
        (
            "overlapping-sections.html",
            "<table><thead><tbody>" + VALID_FUND_ROW + "</tbody></thead></table>",
        ),
        (
            "unclosed-section.html",
            "<table><thead>" + VALID_FUND_ROW + "</table>",
        ),
        (
            "header-only.html",
            "<table><tr><th>Trade date</th><th>Settlement</th><th>Identifier</th>"
            "<th>Market</th><th>Type</th><th>ISIN</th><th>Fund name</th>"
            "<th>Units</th><th>Currency</th><th>Price</th><th>Amount</th></tr></table>",
        ),
    ),
)
@pytest.mark.django_db
def test_invalid_inversis_html_is_rejected_without_creating_batch(
    filename: str, source: str
) -> None:
    user = create_member()
    client = APIClient()
    client.force_login(user)
    account = Account.objects.create(
        workspace=user.memberships.get().workspace,
        name="Synthetic funds",
        kind=Account.Kind.FUNDS,
        external_id="legacy:funds:1",
    )
    response = client.post(
        "/api/fund-orders/upload",
        {
            "account_id": str(account.id),
            "file": SimpleUploadedFile(
                filename,
                source.encode("utf-8"),
                content_type="text/html",
            ),
        },
        HTTP_X_FORWARDED_FOR=filename,
    )

    assert response.status_code == 400
    assert response.json()["error"] == (
        f"El archivo .{filename.rsplit('.', 1)[-1]} subido no es una "
        "exportación HTML de Inversis válida con tabla"
    )
    assert account.import_batches.count() == 0
    assert account.transactions.count() == 0


@pytest.mark.django_db
def test_invalid_inversis_html_is_not_hidden_by_duplicate_batch() -> None:
    user = create_member(language=User.Language.ENGLISH)
    client = APIClient()
    client.force_login(user)
    workspace = user.memberships.get().workspace
    account = Account.objects.create(
        workspace=workspace,
        name="Synthetic funds",
        kind=Account.Kind.FUNDS,
        external_id="legacy:funds:1",
    )
    raw = b"<table><tr><td>open only"
    ImportBatch.objects.create(
        workspace=workspace,
        account=account,
        created_by=user,
        importer_slug="fund_broker",
        source_filename="previous.xls",
        content_sha256=hashlib.sha256(raw).hexdigest(),
        status=ImportBatch.Status.COMPLETED,
        source_rows=1,
    )

    response = client.post(
        "/api/fund-orders/upload",
        {
            "account_id": str(account.id),
            "file": SimpleUploadedFile("malformed.xls", raw, content_type="text/html"),
        },
        HTTP_X_FORWARDED_FOR="duplicate-bypass-test",
    )

    assert response.status_code == 400
    assert response.json()["error"] == (
        "The uploaded .xls file is not a valid Inversis HTML table export"
    )
    assert account.transactions.count() == 0


@pytest.mark.django_db
def test_invalid_inversis_workbook_is_rejected_without_creating_batch() -> None:
    user = create_member(language=User.Language.ENGLISH)
    client = APIClient()
    client.force_login(user)
    account = Account.objects.create(
        workspace=user.memberships.get().workspace,
        name="Synthetic funds",
        kind=Account.Kind.FUNDS,
        external_id="legacy:funds:1",
    )

    response = client.post(
        "/api/fund-orders/upload",
        {
            "account_id": str(account.id),
            "file": SimpleUploadedFile(
                "binary.xls",
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
                content_type="application/vnd.ms-excel",
            ),
        },
        HTTP_X_FORWARDED_FOR="binary-workbook-test",
    )

    assert response.status_code == 400
    assert "Binary Excel workbooks" in response.json()["error"]
    assert account.import_batches.count() == 0
    assert account.transactions.count() == 0
