from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from apps.accounts.models import Account, AccountSnapshot
from apps.api import account_views
from apps.imports.models import ImportBatch, ImportIssue
from apps.market_data.fx import FxConversion
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.mark.django_db(transaction=True)
def test_savings_account_can_be_edited(
    snapshot_context: tuple[APIClient, User],
) -> None:
    client, _ = snapshot_context
    account = client.get("/api/savings/accounts").json()[0]

    response = client.put(
        f"/api/savings/accounts/{account['id']}",
        {
            "name": f"{account['name']} principal",
            "bank": account["bank"],
            "type": account["type"],
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["name"].endswith(" principal")


@pytest.mark.django_db(transaction=True)
def test_savings_snapshot_is_saved_on_last_day_of_month(
    snapshot_context: tuple[APIClient, User],
) -> None:
    client, _ = snapshot_context
    account = client.get("/api/savings/accounts").json()[0]

    response = client.post(
        "/api/savings/history",
        {
            "date": "2028-02-01",
            "account_id": account["id"],
            "balance": 2500,
            "contribution": 100,
            "interest": 4.5,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["date"] == "2028-02-29"


@pytest.mark.django_db(transaction=True)
def test_savings_native_contract_uses_uuid_and_english_fields(
    snapshot_context: tuple[APIClient, User],
) -> None:
    client, _ = snapshot_context
    account = client.get("/api/savings/accounts").json()[0]
    assert set(account) == {"id", "name", "bank", "type", "currency"}
    UUID(account["id"])

    assert client.get("/api/savings/accounts/1").status_code == 404
    assert client.get("/api/savings/history?cuenta_id=1").status_code == 400
    rejected = client.post(
        "/api/savings/history",
        {"fecha": "2028-02-01", "cuenta_id": 1, "saldo": 100},
        format="json",
    )
    assert rejected.status_code == 400

    created = client.post(
        "/api/savings/accounts",
        {"name": "Native savings", "bank": "Native Bank", "type": "Cash"},
        format="json",
    )
    assert created.status_code == 201
    native = created.json()
    assert set(native) == {"id", "name", "bank", "type", "currency"}
    UUID(native["id"])
    assert Account.objects.get(pk=native["id"]).external_id is None

    snapshot = client.post(
        "/api/savings/history",
        {
            "account_id": native["id"],
            "date": "2028-02-01",
            "balance": 2500,
            "contribution": 100,
            "interest": 4.5,
        },
        format="json",
    )
    assert snapshot.status_code == 201
    assert set(snapshot.json()) == {
        "id",
        "account_id",
        "date",
        "balance",
        "balance_original",
        "contribution",
        "contribution_original",
        "interest",
        "interest_original",
        "currency",
        "base_currency",
        "exchange_rate",
        "exchange_rate_date",
        "exchange_rate_source",
    }
    assert snapshot.json()["account_id"] == native["id"]
    assert snapshot.json()["date"] == "2028-02-29"
    assert UUID(snapshot.json()["id"])

    filtered = client.get(f"/api/savings/history?account_id={native['id']}")
    assert filtered.status_code == 200
    assert [item["account_id"] for item in filtered.json()] == [native["id"]]
    assert client.get("/api/summary").json()["total_savings"] == 3500


@pytest.mark.django_db(transaction=True)
def test_savings_native_account_update_delete_and_summary(
    snapshot_context: tuple[APIClient, User],
) -> None:
    client, _ = snapshot_context
    created = client.post(
        "/api/savings/accounts",
        {"name": "Temporary savings", "bank": "Bank", "type": "Cash"},
        format="json",
    )
    account_id = created.json()["id"]
    updated = client.put(
        f"/api/savings/accounts/{account_id}",
        {"name": "Updated savings", "currency": "USD"},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated savings"
    assert updated.json()["currency"] == "USD"
    assert (
        client.put(
            f"/api/savings/accounts/{account_id}",
            {"nombre": "Rejected"},
            format="json",
        ).status_code
        == 400
    )
    assert client.get("/api/summary").status_code == 200
    deleted = client.delete(f"/api/savings/accounts/{account_id}")
    assert deleted.status_code == 200
    assert not Account.objects.filter(pk=account_id).exists()


@pytest.mark.django_db(transaction=True)
def test_savings_native_snapshot_preserves_currency_conversion(
    snapshot_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = snapshot_context
    monkeypatch.setattr(
        account_views,
        "rate_to_base",
        lambda *_args, **_kwargs: FxConversion(Decimal("0.9"), date(2026, 7, 31), "synthetic"),
    )
    account = client.post(
        "/api/savings/accounts",
        {"name": "USD savings", "currency": "USD"},
        format="json",
    ).json()
    response = client.post(
        "/api/savings/history",
        {"account_id": account["id"], "date": "2026-07-01", "balance": 100},
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["date"] == "2026-07-31"
    assert response.json()["balance"] == 90
    assert response.json()["balance_original"] == 100
    assert response.json()["currency"] == "USD"
    assert response.json()["base_currency"] == "EUR"
    assert response.json()["exchange_rate"] == 0.9


@pytest.mark.django_db(transaction=True)
def test_savings_native_rejects_invalid_or_out_of_scope_identifiers(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    account_id = client.get("/api/savings/accounts").json()[0]["id"]
    fund_id = str(Account.objects.get(kind=Account.Kind.FUNDS).id)
    foreign_workspace = Workspace.objects.create(
        name="Foreign workspace", slug="foreign-workspace", base_currency="EUR"
    )
    foreign_account = Account.objects.create(
        workspace=foreign_workspace,
        name="Foreign savings",
        kind=Account.Kind.SAVINGS,
        external_id=None,
    )

    assert client.get("/api/savings/history?account_id=not-a-uuid").status_code == 400
    assert client.get("/api/savings/accounts/not-a-uuid").status_code == 404
    assert (
        client.put(
            f"/api/savings/accounts/{fund_id}",
            {"name": "Wrong type"},
            format="json",
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/savings/accounts/{foreign_account.id}",
            {"name": "Wrong workspace"},
            format="json",
        ).status_code
        == 404
    )
    invalid_date = client.delete(f"/api/savings/history/{account_id}/2026-02-30")
    assert invalid_date.status_code == 400
    assert invalid_date.json()["error"]


@pytest.mark.django_db(transaction=True)
def test_savings_native_account_fields_enforce_model_lengths(
    snapshot_context: tuple[APIClient, User],
) -> None:
    client, _ = snapshot_context
    account_id = client.get("/api/savings/accounts").json()[0]["id"]
    for field, value in (("name", "N" * 161), ("bank", "B" * 161), ("type", "T" * 81)):
        created = client.post(
            "/api/savings/accounts",
            {"name": "Valid", field: value},
            format="json",
        )
        updated = client.put(
            f"/api/savings/accounts/{account_id}",
            {field: value},
            format="json",
        )
        assert created.status_code == 400
        assert updated.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_manual_investment_account_and_snapshot_can_be_updated(
    snapshot_context: tuple[APIClient, User],
) -> None:
    client, _ = snapshot_context
    account = client.get("/api/investments/accounts").json()[0]
    assert set(account) == {"id", "name", "platform", "type", "currency"}
    UUID(account["id"])
    assert (
        client.post(
            "/api/investments/accounts",
            {"nombre": "Legacy account"},
            format="json",
        ).status_code
        == 400
    )

    edited = client.put(
        f"/api/investments/accounts/{account['id']}",
        {
            "name": f"{account['name']} manual",
            "platform": account["platform"],
            "type": account["type"],
        },
        format="json",
    )
    closed = client.post(
        "/api/investments/history",
        {
            "date": "2028-02-01",
            "account_id": account["id"],
            "value": 40000,
            "contribution": 500,
        },
        format="json",
    )

    assert edited.status_code == 200
    assert edited.json()["name"].endswith(" manual")
    assert closed.status_code == 201
    assert closed.json()["date"] == "2028-02-29"
    assert isinstance(closed.json()["interest"], float)
    deleted_history = client.delete(f"/api/investments/history/{account['id']}/2028-02-29")
    assert deleted_history.status_code == 200
    deleted_account = client.delete(f"/api/investments/accounts/{account['id']}")
    assert deleted_account.status_code == 200
    assert not Account.objects.filter(pk=account["id"]).exists()


@pytest.mark.django_db(transaction=True)
def test_manual_investment_native_contract_calculates_or_accepts_interest(
    snapshot_context: tuple[APIClient, User],
) -> None:
    client, _ = snapshot_context
    created = client.post(
        "/api/investments/accounts",
        {"name": "Native investment", "platform": "Broker", "type": "Managed"},
        format="json",
    )
    assert created.status_code == 201
    account = created.json()
    assert set(account) == {"id", "name", "platform", "type", "currency"}
    UUID(account["id"])
    assert Account.objects.get(pk=account["id"]).external_id is None

    first = client.post(
        "/api/investments/history",
        {"account_id": account["id"], "date": "2028-01-01", "value": 1000},
        format="json",
    )
    calculated = client.post(
        "/api/investments/history",
        {
            "account_id": account["id"],
            "date": "2028-02-01",
            "value": 1250,
            "contribution": 100,
        },
        format="json",
    )
    explicit = client.post(
        "/api/investments/history",
        {
            "account_id": account["id"],
            "date": "2028-03-01",
            "value": 1300,
            "contribution": 20,
            "interest": -7.5,
        },
        format="json",
    )

    assert first.status_code == calculated.status_code == explicit.status_code == 201
    assert set(calculated.json()) == {
        "id",
        "account_id",
        "date",
        "value",
        "value_original",
        "contribution",
        "contribution_original",
        "interest",
        "interest_original",
        "currency",
        "base_currency",
        "exchange_rate",
        "exchange_rate_date",
        "exchange_rate_source",
    }
    assert calculated.json()["interest_original"] == 150
    assert explicit.json()["interest_original"] == -7.5
    assert client.get("/api/investments/history?cuenta_id=1").status_code == 400
    filtered = client.get(f"/api/investments/history?account_id={account['id']}")
    assert filtered.status_code == 200
    assert {row["account_id"] for row in filtered.json()} == {account["id"]}


@pytest.mark.django_db(transaction=True)
def test_manual_investment_native_distinguishes_implicit_zero_and_upserts_stably(
    snapshot_context: tuple[APIClient, User],
) -> None:
    client, _ = snapshot_context
    account = client.post(
        "/api/investments/accounts",
        {"name": "Decimal investment", "platform": "Broker"},
        format="json",
    ).json()

    seed = client.post(
        "/api/investments/history",
        {
            "account_id": account["id"],
            "date": "2028-01-01",
            "value": "1000.005",
            "contribution": "0.005",
            "interest": 0,
        },
        format="json",
    )
    implicit = client.post(
        "/api/investments/history",
        {
            "account_id": account["id"],
            "date": "2028-02-01",
            "value": "1100.016",
            "contribution": "100.005",
        },
        format="json",
    )
    explicit_zero = client.post(
        "/api/investments/history",
        {
            "account_id": account["id"],
            "date": "2028-02-15",
            "value": "1100.026",
            "contribution": "100.005",
            "interest": 0,
        },
        format="json",
    )

    assert seed.status_code == implicit.status_code == explicit_zero.status_code == 201
    assert seed.json()["value_original"] == pytest.approx(1000.005)
    assert seed.json()["interest_original"] == 0
    assert implicit.json()["date"] == "2028-02-29"
    assert implicit.json()["value_original"] == pytest.approx(1100.016)
    assert implicit.json()["contribution_original"] == pytest.approx(100.005)
    assert implicit.json()["interest_original"] == pytest.approx(0.01)

    assert explicit_zero.json()["date"] == "2028-02-29"
    assert explicit_zero.json()["id"] == implicit.json()["id"]
    assert explicit_zero.json()["value_original"] == pytest.approx(1100.026)
    assert explicit_zero.json()["interest_original"] == 0
    assert AccountSnapshot.objects.filter(account_id=account["id"], date="2028-02-29").count() == 1


@pytest.mark.django_db(transaction=True)
def test_manual_investment_native_snapshot_preserves_currency_conversion(
    snapshot_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = snapshot_context
    monkeypatch.setattr(
        account_views,
        "rate_to_base",
        lambda *_args, **_kwargs: FxConversion(Decimal("0.9"), date(2028, 1, 31), "synthetic"),
    )
    account = client.post(
        "/api/investments/accounts",
        {"name": "USD investment", "platform": "Broker", "currency": "USD"},
        format="json",
    ).json()
    response = client.post(
        "/api/investments/history",
        {
            "account_id": account["id"],
            "date": "2028-01-01",
            "value": 100,
            "contribution": 10,
            "interest": 5,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["value"] == 90
    assert response.json()["value_original"] == 100
    assert response.json()["contribution"] == 9
    assert response.json()["interest"] == 4.5
    assert response.json()["currency"] == "USD"
    assert response.json()["base_currency"] == "EUR"
    assert response.json()["exchange_rate"] == 0.9


@pytest.mark.django_db(transaction=True)
def test_manual_investment_native_rejects_legacy_and_out_of_scope_identifiers(
    snapshot_context: tuple[APIClient, User],
) -> None:
    client, _ = snapshot_context
    account_id = client.get("/api/investments/accounts").json()[0]["id"]
    savings_id = client.get("/api/savings/accounts").json()[0]["id"]
    foreign_workspace = Workspace.objects.create(
        name="Foreign investment workspace", slug="foreign-investment", base_currency="EUR"
    )
    foreign_account = Account.objects.create(
        workspace=foreign_workspace,
        name="Foreign investment",
        kind=Account.Kind.MANUAL_INVESTMENT,
        external_id=None,
    )

    assert client.get("/api/investments/history?account_id=not-a-uuid").status_code == 400
    assert client.get("/api/investments/accounts/1").status_code == 404
    assert (
        client.put(
            f"/api/investments/accounts/{savings_id}",
            {"name": "Wrong type"},
            format="json",
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/investments/history",
            {"account_id": savings_id, "date": "2028-01-01", "value": 100},
            format="json",
        ).status_code
        == 404
    )
    assert (
        client.get(f"/api/investments/history?account_id={foreign_account.id}").status_code == 404
    )
    assert (
        client.put(
            f"/api/investments/accounts/{foreign_account.id}",
            {"name": "Should remain hidden"},
            format="json",
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/investments/history",
            {"fecha": "2028-01-01", "cuenta_id": account_id, "valor": 100},
            format="json",
        ).status_code
        == 400
    )
    invalid_date = client.delete(f"/api/investments/history/{account_id}/2028-02-30")
    assert invalid_date.status_code == 400
    assert invalid_date.json()["error"]


@pytest.mark.django_db(transaction=True)
def test_manual_investment_native_account_fields_enforce_model_lengths(
    snapshot_context: tuple[APIClient, User],
) -> None:
    client, _ = snapshot_context
    account_id = client.get("/api/investments/accounts").json()[0]["id"]
    for field, value in (
        ("name", "N" * 161),
        ("platform", "P" * 161),
        ("type", "T" * 81),
    ):
        created = client.post(
            "/api/investments/accounts",
            {"name": "Valid", field: value},
            format="json",
        )
        updated = client.put(
            f"/api/investments/accounts/{account_id}",
            {field: value},
            format="json",
        )
        assert created.status_code == 400
        assert updated.status_code == 400


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "endpoint",
    ("/api/fund-accounts", "/api/stock-accounts", "/api/crypto-accounts"),
)
def test_traded_account_crud_uses_strict_native_contract(
    traded_context: tuple[APIClient, User], endpoint: str
) -> None:
    client, _ = traded_context
    body = {
        "name": "Synthetic account",
        "platform": "Synthetic broker",
        "type": "Managed",
        "currency": "EUR",
        "importer_slug": "none",
    }

    created = client.post(endpoint, body, format="json")

    assert created.status_code == 201
    account = created.json()
    UUID(account["id"])
    assert set(account) == {
        "id",
        "name",
        "platform",
        "type",
        "currency",
        "importer_slug",
        "importer_name",
    }
    assert account == {
        "id": account["id"],
        "name": "Synthetic account",
        "platform": "Synthetic broker",
        "type": "Managed",
        "currency": "EUR",
        "importer_slug": "",
        "importer_name": "",
    }

    updated = client.put(
        f"{endpoint}/{account['id']}",
        {"name": "Updated account", "platform": "Updated broker"},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated account"
    assert updated.json()["platform"] == "Updated broker"

    for invalid in (
        {**body, "nombre": "Legacy name"},
        {**body, "unknown": "rejected"},
    ):
        rejected = client.post(endpoint, invalid, format="json")
        assert rejected.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_savings_write_persists_to_database(
    snapshot_context: tuple[APIClient, User],
) -> None:
    client, _ = snapshot_context

    response = client.post(
        "/api/savings/history",
        {
            "date": "2026-07-31",
            "account_id": client.get("/api/savings/accounts").json()[0]["id"],
            "balance": 1234.56,
            "contribution": 10,
        },
        format="json",
    )

    assert response.status_code == 201
    assert AccountSnapshot.objects.get(
        date="2026-07-31",
        account__kind=Account.Kind.SAVINGS,
    ).value == Decimal("1234.56")


@pytest.mark.django_db(transaction=True)
def test_traded_account_delete_removes_import_dependents_atomically(
    traded_context: tuple[APIClient, User],
) -> None:
    client, user = traded_context
    account = Account.objects.get(kind=Account.Kind.CRYPTO)
    raw = (
        b"txid,pair,time,type,price,cost,fee,vol\n"
        b"delete-me,BTC/EUR,2026-07-22 12:00:00,buy,100000,100,1,0.001\n"
    )
    imported = client.post(
        "/api/crypto-orders/upload-kraken-pro",
        {
            "account_id": str(account.id),
            "file": SimpleUploadedFile("trades.csv", raw, content_type="text/csv"),
        },
    )
    assert imported.status_code == 200
    batch = ImportBatch.objects.get(account=account)
    imported_transaction = Transaction.objects.get(external_id="delete-me")
    issue = ImportIssue.objects.create(
        batch=batch,
        severity=ImportIssue.Severity.WARNING,
        code="test-warning",
        message="Synthetic warning",
    )
    account_id = str(account.id)
    destination = client.post(
        "/api/crypto-accounts",
        {"name": "Destination", "platform": "Synthetic", "importer_slug": "none"},
        format="json",
    ).json()
    moved = client.put(
        f"/api/crypto-orders/{imported_transaction.id}",
        {
            "account_id": destination["id"],
            "symbol": "BTC",
            "trade_date": "2026-07-22",
            "operation_type": "buy",
            "quantity": "0.001",
            "unit_price": "100000",
            "net_amount": "101",
            "fee": "1",
            "currency": "EUR",
        },
        format="json",
    )
    assert moved.status_code == 200

    deleted = client.delete(f"/api/crypto-accounts/{account_id}")

    assert deleted.status_code == 200
    assert not Account.objects.filter(pk=account_id).exists()
    assert not Transaction.objects.filter(account_id=account_id).exists()
    assert not ImportBatch.objects.filter(pk=batch.pk).exists()
    assert not ImportIssue.objects.filter(pk=issue.pk).exists()
    assert not ImportBatch.objects.filter(workspace=user.memberships.get().workspace).exists()
    moved_transaction = Transaction.objects.get(external_id="delete-me")
    assert str(moved_transaction.account_id) == destination["id"]
    assert moved_transaction.import_batch_id is None


@pytest.mark.django_db(transaction=True)
def test_traded_account_scope_and_roles_cover_archived_foreign_and_viewer_rows(
    traded_context: tuple[APIClient, User],
) -> None:
    client, user = traded_context
    workspace = user.memberships.get().workspace
    archived = Account.objects.create(
        workspace=workspace,
        name="Archived funds",
        kind=Account.Kind.FUNDS,
        importer_slug="fund_broker",
        currency="EUR",
        archived_at=timezone.now(),
    )
    foreign_workspace = Workspace.objects.create(name="Foreign", slug="foreign-scope")
    foreign = Account.objects.create(
        workspace=foreign_workspace,
        name="Foreign funds",
        kind=Account.Kind.FUNDS,
        importer_slug="fund_broker",
        currency="EUR",
    )
    for account in (archived, foreign):
        account_id = str(account.id)
        assert (
            client.put(
                f"/api/fund-accounts/{account_id}",
                {"name": "Should remain hidden"},
                format="json",
            ).status_code
            == 404
        )
        deleted_fund = client.delete(f"/api/fund-accounts/{account_id}")
        assert deleted_fund.status_code == 404
        assert client.get(f"/api/orders?account_id={account_id}").status_code == 404
        assert (
            client.post(
                f"/api/account-imports/funds/{account_id}",
                {"file": SimpleUploadedFile("funds.csv", b"not used")},
            ).status_code
            == 404
        )

    viewer = User.objects.create_user(email="viewer@example.com", password="viewer-password")
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=viewer,
        role=WorkspaceMembership.Role.VIEWER,
    )
    viewer_client = APIClient()
    viewer_client.force_authenticate(viewer)
    assert (
        viewer_client.post(
            "/api/fund-accounts",
            {"name": "Viewer account", "platform": "Broker", "importer_slug": "none"},
            format="json",
        ).status_code
        == 403
    )
    viewer_delete = viewer_client.delete(f"/api/fund-accounts/{archived.id}")
    assert viewer_delete.status_code == 403

    editor = User.objects.create_user(email="editor@example.com", password="editor-password")
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=editor,
        role=WorkspaceMembership.Role.EDITOR,
    )
    editor_client = APIClient()
    editor_client.force_authenticate(editor)
    created = editor_client.post(
        "/api/fund-accounts",
        {"name": "Editor account", "platform": "Broker", "importer_slug": "none"},
        format="json",
    )
    assert created.status_code == 201
    editor_delete = editor_client.delete(f"/api/fund-accounts/{created.json()['id']}")
    assert editor_delete.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_crypto_accounts_can_be_created_and_filter_orders(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    created = client.post(
        "/api/crypto-accounts",
        {
            "name": "Cuenta secundaria",
            "platform": "Otro exchange",
            "importer_slug": "none",
        },
        format="json",
    )

    assert created.status_code == 201
    account_id = created.json()["id"]
    assert created.json()["platform"] == "Otro exchange"

    source = Transaction.objects.filter(
        account__kind=Account.Kind.CRYPTO,
        instrument__kind="crypto",
    ).first()
    assert source is not None
    account = Account.objects.get(pk=account_id)
    Transaction.objects.create(
        account=account,
        instrument=source.instrument,
        external_id="secondary-account-order",
        trade_date=source.trade_date,
        settlement_date=source.settlement_date,
        operation_type=source.operation_type,
        cash_flow_type=source.cash_flow_type,
        quantity=source.quantity,
        unit_price=source.unit_price,
        net_amount=source.net_amount,
        fee=source.fee,
        currency=source.currency,
        market=source.market,
        provider_operation_type=source.provider_operation_type,
        raw_metadata=source.raw_metadata,
    )

    orders = client.get(f"/api/crypto-orders?account_id={account_id}")
    analysis = client.get(f"/api/crypto-analysis?account_id={account_id}")

    assert orders.status_code == 200
    assert [row["account_id"] for row in orders.json()] == [account_id]
    assert orders.json()[0]["account_name"] == "Cuenta secundaria"
    assert orders.json()[0]["platform"] == "Otro exchange"
    assert analysis.status_code == 200
    assert analysis.json()[0]["instrument_id"] == str(source.instrument_id)
