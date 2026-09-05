from uuid import UUID

import pytest
from apps.accounts.models import Account
from apps.transactions.models import Transaction
from apps.users.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient


@pytest.mark.django_db(transaction=True)
def test_registered_parser_upload_is_persisted_and_deduplicated(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    content = (
        b"txid,pair,time,type,price,cost,fee,vol\n"
        b"new-tx,BTC/EUR,2026-07-20 12:00:00,buy,100000,100,1,0.001\n"
    )
    uploaded = SimpleUploadedFile("trades.csv", content, content_type="text/csv")

    response = client.post(
        "/api/crypto-orders/upload-kraken-pro",
        {"account_id": str(Account.objects.get(kind=Account.Kind.CRYPTO).id), "file": uploaded},
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert Transaction.objects.filter(external_id="new-tx").exists()
    imported = Transaction.objects.get(external_id="new-tx")
    assert UUID(str(imported.id))
    listed = client.get("/api/crypto-orders")
    assert listed.status_code == 200
    listed_row = next(row for row in listed.json() if row["id"] == str(imported.id))
    assert "operacion_id" not in listed_row
    assert {
        "id",
        "account_id",
        "asset_name",
        "trade_date",
        "operation_type",
        "cash_flow_type",
        "quantity",
        "unit_price",
        "net_amount",
        "fee",
        "currency",
    } <= set(listed_row)
    assert not {
        "external_id",
        "raw_metadata",
        "import_batch",
        "fecha_operacion",
        "tipo_operacion",
        "titulos",
        "precio_compra",
        "importe_neto",
        "comision",
    } & set(listed_row)

    duplicate = SimpleUploadedFile("again.csv", content, content_type="text/csv")
    response = client.post(
        "/api/crypto-orders/upload-kraken-pro",
        {"account_id": str(Account.objects.get(kind=Account.Kind.CRYPTO).id), "file": duplicate},
    )
    assert response.json()["duplicate"] is True


@pytest.mark.django_db(transaction=True)
def test_account_importer_is_required_compatible_and_drives_the_upload(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context

    missing = client.post(
        "/api/crypto-accounts",
        {"name": "Sin decidir", "platform": "Otro exchange"},
        format="json",
    )
    incompatible = client.post(
        "/api/crypto-accounts",
        {
            "name": "Importador incorrecto",
            "platform": "Otro exchange",
            "importer_slug": "trade_republic",
        },
        format="json",
    )

    assert missing.status_code == 400
    assert missing.json()["error"] == "Selecciona el importador de la cuenta"
    assert incompatible.status_code == 400
    assert "no es compatible" in incompatible.json()["error"]

    account = next(
        item
        for item in client.get("/api/crypto-accounts").json()
        if item["importer_slug"] == "kraken_spot"
    )
    content = (
        b"txid,pair,time,type,price,cost,fee,vol\n"
        b"bound-tx,BTC/EUR,2026-07-21 12:00:00,buy,100000,100,1,0.001\n"
    )
    response = client.post(
        f"/api/account-imports/crypto/{account['id']}",
        {"file": SimpleUploadedFile("trades.csv", content, content_type="text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1
    batch = Transaction.objects.get(external_id="bound-tx").import_batch
    assert batch is not None
    assert batch.importer_slug == "kraken_spot"


@pytest.mark.django_db(transaction=True)
def test_upload_contract_distinguishes_direct_and_account_bound_multipart(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    account = Account.objects.get(kind=Account.Kind.CRYPTO)
    raw = b"not parsed because the multipart contract is rejected first"

    direct_unknown = client.post(
        "/api/crypto-orders/upload-kraken-pro",
        {
            "account_id": str(account.id),
            "file": SimpleUploadedFile("trades.csv", raw, content_type="text/csv"),
            "unexpected": "field",
        },
    )
    bound_account = client.post(
        f"/api/account-imports/crypto/{account.id}",
        {
            "file": SimpleUploadedFile("trades.csv", raw, content_type="text/csv"),
            "account_id": str(account.id),
        },
    )
    bound_unknown = client.post(
        f"/api/account-imports/crypto/{account.id}",
        {
            "file": SimpleUploadedFile("trades.csv", raw, content_type="text/csv"),
            "unexpected": "field",
        },
    )
    unknown_kind = client.post(
        f"/api/account-imports/not-a-kind/{account.id}",
        {"file": SimpleUploadedFile("trades.csv", raw, content_type="text/csv")},
    )

    assert direct_unknown.status_code == 400
    assert bound_account.status_code == 400
    assert bound_unknown.status_code == 400
    assert unknown_kind.status_code == 400
