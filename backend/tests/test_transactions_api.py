from decimal import Decimal
from uuid import UUID

import pytest
from apps.accounts.models import Account
from apps.imports.models import ImportBatch
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
)
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from django.db import IntegrityError
from rest_framework.test import APIClient


@pytest.mark.django_db(transaction=True)
def test_transaction_detail_is_scoped_by_uuid_and_workspace_kind(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    source = Transaction.objects.filter(account__kind=Account.Kind.STOCKS).first()
    assert source is not None
    first_account = source.account
    second_account = Account.objects.create(
        workspace=first_account.workspace,
        name="Second stock account",
        kind=Account.Kind.STOCKS,
        currency="EUR",
    )
    duplicate = Transaction.objects.create(
        account=second_account,
        instrument=source.instrument,
        external_id="shared-provider-id",
        trade_date="2026-01-01",
        operation_type=Transaction.OperationType.BUY,
        cash_flow_type=Transaction.CashFlowType.NONE,
        quantity=1,
        unit_price=10,
        net_amount=10,
        fee=0,
        currency="EUR",
        provider_operation_type="Compra",
    )
    source.external_id = duplicate.external_id
    source.save(update_fields=("external_id",))
    isin = source.instrument.identifiers.get(scheme=InstrumentIdentifier.Scheme.ISIN).value
    update_payload = {
        "account_id": str(first_account.id),
        "isin": isin,
        "trade_date": "2026-02-02",
        "operation_type": "buy",
        "quantity": "1",
        "unit_price": "10",
        "net_amount": "10",
        "fee": "0",
        "currency": "EUR",
    }

    updated = client.put(f"/api/stock-orders/{source.id}", update_payload, format="json")
    assert updated.status_code == 200
    source.refresh_from_db()
    duplicate.refresh_from_db()
    assert source.trade_date.isoformat() == "2026-02-02"
    assert duplicate.trade_date.isoformat() == "2026-01-01"

    deleted = client.delete(f"/api/stock-orders/{duplicate.id}")
    assert deleted.status_code == 200
    assert Transaction.objects.filter(pk=source.pk).exists()
    deleted_source = client.delete(f"/api/stock-orders/{source.id}")
    assert deleted_source.status_code == 200
    assert not Transaction.objects.filter(pk=source.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_transaction_move_rejects_duplicate_external_id_without_mutation(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    source = Transaction.objects.filter(account__kind=Account.Kind.STOCKS).first()
    assert source is not None
    source_account = source.account
    target_account = Account.objects.create(
        workspace=source_account.workspace,
        name="Duplicate target account",
        kind=Account.Kind.STOCKS,
        currency="EUR",
    )
    source.external_id = "shared-provider-move"
    source_batch = ImportBatch.objects.create(
        workspace=source_account.workspace,
        account=source_account,
        importer_slug="synthetic",
        source_filename="source.csv",
        content_sha256="a" * 64,
        status=ImportBatch.Status.COMPLETED,
        source_rows=1,
        imported_rows=1,
    )
    source.import_batch = source_batch
    source.save(update_fields=("external_id", "import_batch"))
    target_batch = ImportBatch.objects.create(
        workspace=target_account.workspace,
        account=target_account,
        importer_slug="synthetic",
        source_filename="target.csv",
        content_sha256="b" * 64,
        status=ImportBatch.Status.COMPLETED,
        source_rows=1,
        imported_rows=1,
    )
    duplicate = Transaction.objects.create(
        account=target_account,
        instrument=source.instrument,
        import_batch=target_batch,
        external_id=source.external_id,
        trade_date=source.trade_date,
        operation_type=source.operation_type,
        cash_flow_type=source.cash_flow_type,
        quantity=source.quantity,
        unit_price=source.unit_price,
        net_amount=source.net_amount,
        fee=source.fee,
        currency="EUR",
    )
    isin = source.instrument.identifiers.get(scheme=InstrumentIdentifier.Scheme.ISIN).value
    failed = client.put(
        f"/api/stock-orders/{source.id}",
        {
            "account_id": str(target_account.id),
            "isin": isin,
            "trade_date": "2026-02-02",
            "operation_type": "buy",
            "quantity": "1",
            "unit_price": "10",
            "net_amount": "10",
            "fee": "0",
            "currency": "EUR",
        },
        format="json",
    )

    assert failed.status_code == 400
    source.refresh_from_db()
    duplicate.refresh_from_db()
    assert source.account_id == source_account.id
    assert source.import_batch_id == source_batch.id
    assert source.external_id == "shared-provider-move"
    assert duplicate.account_id == target_account.id
    assert duplicate.import_batch_id == target_batch.id
    assert duplicate.external_id == "shared-provider-move"
    assert ImportBatch.objects.filter(pk=source_batch.id, account=source_account).exists()
    assert ImportBatch.objects.filter(pk=target_batch.id, account=target_account).exists()


@pytest.mark.django_db(transaction=True)
def test_manual_fund_canonical_operations_drive_positions_and_source_history(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    account = Account.objects.get(kind=Account.Kind.FUNDS)
    instrument = Instrument.objects.get(kind=Instrument.Kind.FUND)
    isin = instrument.identifiers.get(scheme=InstrumentIdentifier.Scheme.ISIN).value
    payload = {
        "account_id": str(account.id),
        "isin": isin,
        "trade_date": "2026-02-01",
        "settlement_date": "2026-02-02",
        "operation_type": "buy",
        "quantity": "2",
        "unit_price": "10",
        "net_amount": "20",
        "fee": "0",
        "currency": "EUR",
    }

    created = client.post("/api/orders", payload, format="json")

    assert created.status_code == 201, created.content
    created_row = created.json()
    assert created_row["operation_type"] == "buy"
    assert created_row["provider_operation_type"] == "SUSCRIPCION"
    transaction_id = created_row["id"]
    position_after_buy = client.get(f"/api/fund-analysis?account_id={account.id}")
    assert position_after_buy.status_code == 200
    assert position_after_buy.json()[0]["quantity"] == pytest.approx(12)

    edited = client.put(
        f"/api/orders/{transaction_id}",
        {**payload, "operation_type": "sell", "quantity": "2", "net_amount": "20"},
        format="json",
    )

    assert edited.status_code == 200, edited.content
    edited_row = edited.json()
    assert edited_row["operation_type"] == "sell"
    assert edited_row["provider_operation_type"] == "REEMBOLSO"
    position_after_sell = client.get(f"/api/fund-analysis?account_id={account.id}")
    assert position_after_sell.status_code == 200
    assert position_after_sell.json()[0]["quantity"] == pytest.approx(8)

    portfolio = client.get("/api/portfolio-analysis")
    assert portfolio.status_code == 200
    fund_item = next(
        item
        for item in portfolio.json()["items"]
        if item["origen"] == "fund" and item["cuenta_id"].endswith(str(account.id))
    )
    assert fund_item["valor"] == pytest.approx(88)

    assert (
        client.patch(
            "/api/auth/preferences", {"summary_sources": ["funds"]}, format="json"
        ).status_code
        == 200
    )
    history = client.get("/api/net-worth-history")
    assert history.status_code == 200
    assert history.json()[-1]["source_totals"]["funds"] == pytest.approx(88)


@pytest.mark.django_db(transaction=True)
def test_imported_transaction_edit_preserves_provider_provenance_and_batch_policy(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    source = Transaction.objects.filter(account__kind=Account.Kind.STOCKS).first()
    assert source is not None
    source_account = source.account
    source.external_id = "provider-provenance-001"
    source.provider_operation_type = "Provider-specific buy label"
    source.raw_metadata = {
        "legacy_name": "Imported stock label",
        "provider_field": "must survive edits",
    }
    source_batch = ImportBatch.objects.create(
        workspace=source_account.workspace,
        account=source_account,
        importer_slug="synthetic",
        source_filename="provenance.csv",
        content_sha256="e" * 64,
        status=ImportBatch.Status.COMPLETED,
        source_rows=1,
        imported_rows=1,
    )
    source.import_batch = source_batch
    source.save(
        update_fields=("external_id", "provider_operation_type", "raw_metadata", "import_batch")
    )
    isin = source.instrument.identifiers.get(scheme=InstrumentIdentifier.Scheme.ISIN).value
    edit_payload = {
        "account_id": str(source_account.id),
        "isin": isin,
        "trade_date": "2026-03-02",
        "operation_type": "buy",
        "quantity": "3",
        "unit_price": "60",
        "net_amount": "180",
        "fee": "0",
        "currency": "EUR",
    }

    edited = client.put(f"/api/stock-orders/{source.id}", edit_payload, format="json")

    assert edited.status_code == 200, edited.content
    source.refresh_from_db()
    assert source.external_id == "provider-provenance-001"
    assert source.provider_operation_type == "Provider-specific buy label"
    assert source.raw_metadata == {
        "legacy_name": "Imported stock label",
        "provider_field": "must survive edits",
    }
    assert source.import_batch_id == source_batch.id
    stock_analysis = client.get(f"/api/stock-analysis?account_id={source_account.id}")
    assert stock_analysis.status_code == 200
    assert stock_analysis.json()[0]["quantity"] == pytest.approx(3)

    target_account = Account.objects.create(
        workspace=source_account.workspace,
        name="Provenance target",
        kind=Account.Kind.STOCKS,
        currency="EUR",
    )
    moved = client.put(
        f"/api/stock-orders/{source.id}",
        {**edit_payload, "account_id": str(target_account.id), "operation_type": "buy"},
        format="json",
    )

    assert moved.status_code == 200, moved.content
    source.refresh_from_db()
    assert source.account_id == target_account.id
    assert source.external_id == "provider-provenance-001"
    assert source.provider_operation_type == "Provider-specific buy label"
    assert source.raw_metadata == {
        "legacy_name": "Imported stock label",
        "provider_field": "must survive edits",
    }
    assert source.import_batch_id is None
    assert ImportBatch.objects.filter(pk=source_batch.id, account=source_account).exists()


@pytest.mark.django_db(transaction=True)
def test_transaction_move_handles_raced_external_id_conflict_atomically(
    traded_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = traded_context
    source = Transaction.objects.filter(account__kind=Account.Kind.STOCKS).first()
    assert source is not None
    source_account = source.account
    source_trade_date = source.trade_date
    source_amount = source.net_amount
    target_account = Account.objects.create(
        workspace=source_account.workspace,
        name="Raced target account",
        kind=Account.Kind.STOCKS,
        currency="EUR",
    )
    source.external_id = "raced-provider-move"
    source_batch = ImportBatch.objects.create(
        workspace=source_account.workspace,
        account=source_account,
        importer_slug="synthetic",
        source_filename="raced-source.csv",
        content_sha256="c" * 64,
        status=ImportBatch.Status.COMPLETED,
        source_rows=1,
        imported_rows=1,
    )
    source.import_batch = source_batch
    source.save(update_fields=("external_id", "import_batch"))

    def raise_external_id_conflict(*_args: object, **_kwargs: object) -> None:
        raise IntegrityError(
            "UNIQUE constraint failed: "
            f"{Transaction._meta.db_table}.account_id, "
            f"{Transaction._meta.db_table}.external_id"
        )

    monkeypatch.setattr(Transaction, "save", raise_external_id_conflict)
    isin = source.instrument.identifiers.get(scheme=InstrumentIdentifier.Scheme.ISIN).value
    failed = client.put(
        f"/api/stock-orders/{source.id}",
        {
            "account_id": str(target_account.id),
            "isin": isin,
            "trade_date": "2026-02-03",
            "operation_type": "buy",
            "quantity": "2",
            "unit_price": "11",
            "net_amount": "22",
            "fee": "0",
            "currency": "EUR",
        },
        format="json",
    )

    assert failed.status_code == 400
    source.refresh_from_db()
    assert source.account_id == source_account.id
    assert source.import_batch_id == source_batch.id
    assert source.external_id == "raced-provider-move"
    assert source.trade_date == source_trade_date
    assert source.net_amount == source_amount
    assert ImportBatch.objects.filter(pk=source_batch.id, account=source_account).exists()
    assert not Transaction.objects.filter(account=target_account).exists()


@pytest.mark.django_db(transaction=True)
def test_transaction_move_reraises_unrelated_integrity_error_without_mutation(
    traded_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = traded_context
    source = Transaction.objects.filter(account__kind=Account.Kind.STOCKS).first()
    assert source is not None
    source_account = source.account
    source_trade_date = source.trade_date
    source_amount = source.net_amount
    target_account = Account.objects.create(
        workspace=source_account.workspace,
        name="Unrelated error target account",
        kind=Account.Kind.STOCKS,
        currency="EUR",
    )
    source.external_id = "unrelated-provider-move"
    source_batch = ImportBatch.objects.create(
        workspace=source_account.workspace,
        account=source_account,
        importer_slug="synthetic",
        source_filename="unrelated-source.csv",
        content_sha256="d" * 64,
        status=ImportBatch.Status.COMPLETED,
        source_rows=1,
        imported_rows=1,
    )
    source.import_batch = source_batch
    source.save(update_fields=("external_id", "import_batch"))

    def raise_unrelated_error(*_args: object, **_kwargs: object) -> None:
        raise IntegrityError("CHECK constraint failed: transaction_quantity_positive")

    monkeypatch.setattr(Transaction, "save", raise_unrelated_error)
    isin = source.instrument.identifiers.get(scheme=InstrumentIdentifier.Scheme.ISIN).value
    with pytest.raises(IntegrityError, match="transaction_quantity_positive"):
        client.put(
            f"/api/stock-orders/{source.id}",
            {
                "account_id": str(target_account.id),
                "isin": isin,
                "trade_date": "2026-02-04",
                "operation_type": "buy",
                "quantity": "3",
                "unit_price": "12",
                "net_amount": "36",
                "fee": "0",
                "currency": "EUR",
            },
            format="json",
        )

    source.refresh_from_db()
    assert source.account_id == source_account.id
    assert source.import_batch_id == source_batch.id
    assert source.external_id == "unrelated-provider-move"
    assert source.trade_date == source_trade_date
    assert source.net_amount == source_amount
    assert ImportBatch.objects.filter(pk=source_batch.id, account=source_account).exists()
    assert not Transaction.objects.filter(account=target_account).exists()


@pytest.mark.django_db(transaction=True)
def test_transaction_uuid_detail_enforces_workspace_kind_and_roles(
    traded_context: tuple[APIClient, User],
) -> None:
    client, user = traded_context
    source = Transaction.objects.filter(account__kind=Account.Kind.STOCKS).first()
    assert source is not None
    workspace = user.memberships.get().workspace
    foreign_workspace = Workspace.objects.create(name="Foreign transaction workspace")
    foreign_account = Account.objects.create(
        workspace=foreign_workspace,
        name="Foreign stock account",
        kind=Account.Kind.STOCKS,
        currency="EUR",
    )
    foreign_transaction = Transaction.objects.create(
        account=foreign_account,
        instrument=source.instrument,
        trade_date=source.trade_date,
        operation_type=source.operation_type,
        cash_flow_type=source.cash_flow_type,
        quantity=source.quantity,
        unit_price=source.unit_price,
        net_amount=source.net_amount,
        fee=source.fee,
        currency="EUR",
    )

    unsupported_method = client.get(f"/api/stock-orders/{source.id}")
    assert unsupported_method.status_code == 405
    foreign_delete = client.delete(f"/api/stock-orders/{foreign_transaction.id}")
    assert foreign_delete.status_code == 404
    cross_kind_delete = client.delete(f"/api/crypto-orders/{source.id}")
    assert cross_kind_delete.status_code == 404
    invalid_uuid_delete = client.delete("/api/stock-orders/not-a-uuid")
    assert invalid_uuid_delete.status_code == 404

    viewer = User.objects.create_user(email="transaction-viewer@example.com")
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=viewer,
        role=WorkspaceMembership.Role.VIEWER,
    )
    viewer_client = APIClient()
    viewer_client.force_authenticate(viewer)
    viewer_delete = viewer_client.delete(f"/api/stock-orders/{source.id}")
    assert viewer_delete.status_code == 403


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("endpoint", "account_kind", "asset_key", "asset_value", "price_key", "operation"),
    (
        ("/api/orders", Account.Kind.FUNDS, "isin", "SYNTH-FUND-001", "unit_price", "buy"),
        (
            "/api/stock-orders",
            Account.Kind.STOCKS,
            "isin",
            "SYNTH-STOCK-001",
            "unit_price",
            "buy",
        ),
        ("/api/crypto-orders", Account.Kind.CRYPTO, "symbol", "BTC", "unit_price", "buy"),
    ),
)
def test_manual_traded_transactions_validate_native_typed_contract(
    traded_context: tuple[APIClient, User],
    endpoint: str,
    account_kind: str,
    asset_key: str,
    asset_value: str,
    price_key: str,
    operation: str,
) -> None:
    client, _ = traded_context
    account = Account.objects.get(kind=account_kind)
    payload: dict[str, object] = {
        "account_id": str(account.id),
        asset_key: asset_value,
        "trade_date": "2026-07-25",
        "operation_type": operation,
        "quantity": "2.5",
        price_key: "40",
        "net_amount": "100",
        "fee": "0.5",
        "currency": "EUR",
        "fx_rate_to_base": "1",
        "fx_rate_date": "2026-07-25",
        "fx_source": "identity",
        "market": "Synthetic market",
    }
    if account_kind == Account.Kind.FUNDS:
        payload["settlement_date"] = ""
    if account_kind == Account.Kind.STOCKS:
        payload["is_saveback"] = True

    created = client.post(endpoint, payload, format="json")

    assert created.status_code == 201, created.content
    public = created.json()
    transaction_row = Transaction.objects.get(pk=public["id"])
    assert "operacion_id" not in public
    assert not {"external_id", "raw_metadata", "import_batch"} & set(public)
    assert {
        "id",
        "account_id",
        "account_name",
        "platform",
        "asset_name",
        "trade_date",
        "settlement_date",
        "operation_type",
        "cash_flow_type",
        "quantity",
        "unit_price",
        "net_amount",
        "fee",
        "currency",
        "base_currency",
        "base_unit_price",
        "base_net_amount",
        "base_fee",
        "fx_rate_to_base",
        "fx_rate_date",
        "fx_source",
        "market",
        "provider_operation_type",
    } <= set(public)
    assert not {
        "fecha_operacion",
        "fecha_liquidacion",
        "tipo_operacion",
        "titulos",
        "precio_neto",
        "precio_compra",
        "importe_neto",
        "comision",
        "cuenta_id",
        "cuenta_nombre",
        "plataforma",
        "moneda",
        "moneda_base",
    } & set(public)
    assert transaction_row.external_id is None
    assert transaction_row.account_id == account.id
    assert transaction_row.market == "Synthetic market"
    assert transaction_row.fx_rate_to_base == Decimal("1")
    if account_kind == Account.Kind.FUNDS:
        assert transaction_row.settlement_date is None

    for invalid_field, invalid_value in (
        ("unknown", "rejected"),
        ("fecha_operacion", "2026-07-25"),
        ("tipo_operacion", "Compra"),
        ("titulos", "1"),
        ("precio_neto", "40"),
        ("importe_neto", "100"),
        ("comision", "0"),
        ("divisa", "EUR"),
        ("cuenta_id", "1"),
        ("cuenta_id_original", "1"),
    ):
        invalid = {**payload, invalid_field: invalid_value}
        rejected = client.post(endpoint, invalid, format="json")
        assert rejected.status_code == 400, (invalid_field, rejected.content)


@pytest.mark.django_db(transaction=True)
def test_fund_and_crypto_movements_can_be_created_and_edited_manually(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    fund_account = client.get("/api/fund-accounts").json()[0]
    fund = client.get("/api/funds").json()[0]
    fund_isin = next(item["value"] for item in fund["identifiers"] if item["scheme"] == "isin")

    created_fund = client.post(
        "/api/orders",
        {
            "account_id": fund_account["id"],
            "isin": fund_isin,
            "trade_date": "2026-07-25",
            "settlement_date": "2026-07-26",
            "operation_type": "buy",
            "quantity": 2,
            "unit_price": 50,
            "net_amount": 100,
        },
        format="json",
    )

    assert created_fund.status_code == 201
    fund_id = created_fund.json()["id"]
    assert UUID(fund_id)
    assert Transaction.objects.get(pk=fund_id).external_id is None
    updated_fund = client.put(
        f"/api/orders/{fund_id}",
        {
            "account_id": fund_account["id"],
            "isin": fund_isin,
            "trade_date": "2026-07-25",
            "settlement_date": "2026-07-27",
            "operation_type": "sell",
            "quantity": 1,
            "unit_price": 55,
            "net_amount": 55,
        },
        format="json",
    )
    assert updated_fund.status_code == 200
    assert updated_fund.json()["operation_type"] == "sell"
    assert updated_fund.json()["net_amount"] == 55

    crypto_account = client.get("/api/crypto-accounts").json()[0]
    crypto = client.get("/api/cryptos").json()[0]
    crypto_symbol = next(
        item["value"] for item in crypto["identifiers"] if item["scheme"] == "crypto_symbol"
    )
    created_crypto = client.post(
        "/api/crypto-orders",
        {
            "account_id": crypto_account["id"],
            "symbol": crypto_symbol,
            "trade_date": "2026-07-25",
            "operation_type": "buy",
            "quantity": 0.001,
            "unit_price": 70000,
            "net_amount": 70.5,
            "fee": 0.5,
        },
        format="json",
    )

    assert created_crypto.status_code == 201
    assert created_crypto.json()["operation_type"] == "buy"
    assert created_crypto.json()["fee"] == 0.5


@pytest.mark.django_db(transaction=True)
def test_stock_cashback_is_only_available_for_trade_republic(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    trade_republic = client.get("/api/stock-accounts").json()[0]
    stock = client.get("/api/stocks").json()[0]
    stock_isin = next(item["value"] for item in stock["identifiers"] if item["scheme"] == "isin")

    created = client.post(
        "/api/stock-orders",
        {
            "account_id": trade_republic["id"],
            "isin": stock_isin,
            "trade_date": "2026-07-25",
            "operation_type": "buy",
            "quantity": 1,
            "unit_price": 25,
            "net_amount": 25,
            "fee": 0,
            "is_saveback": True,
        },
        format="json",
    )

    assert created.status_code == 201
    assert created.json()["is_saveback"] is True

    other_account = client.post(
        "/api/stock-accounts",
        {
            "name": "Broker secundario",
            "platform": "Otro broker",
            "importer_slug": "none",
        },
        format="json",
    ).json()
    rejected_cashback = client.post(
        "/api/stock-orders",
        {
            "account_id": other_account["id"],
            "isin": stock_isin,
            "trade_date": "2026-07-25",
            "operation_type": "buy",
            "quantity": 1,
            "unit_price": 25,
            "net_amount": 25,
            "fee": 0,
            "is_saveback": True,
        },
        format="json",
    )

    assert rejected_cashback.status_code == 201
    assert rejected_cashback.json()["is_saveback"] is False

    regular = client.get(f"/api/stock-analysis?account_id={trade_republic['id']}").json()
    cashback_as_benefit = client.get(
        f"/api/stock-analysis?account_id={trade_republic['id']}&ignore_savebacks=true"
    ).json()
    regular_cost = sum(row["cost"] for row in regular)
    benefit_cost = sum(row["cost"] for row in cashback_as_benefit)
    assert benefit_cost < regular_cost
