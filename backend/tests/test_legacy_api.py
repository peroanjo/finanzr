from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from apps.accounts.models import Account, AccountSnapshot
from apps.api import views
from apps.common.models import InstallationSettings
from apps.imports.legacy_service import LegacyImportService
from apps.market_data.fx import FxConversion
from apps.market_data.models import MarketPrice, WorkspaceInstrument
from apps.transactions.models import Transaction
from apps.users.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from .legacy_fixture import write_legacy_fixture


@pytest.fixture(scope="session")
def legacy_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_legacy_fixture(tmp_path_factory.mktemp("legacy-data"))


@pytest.fixture
def imported_api(legacy_data_dir: Path) -> tuple[APIClient, User]:
    LegacyImportService(
        data_dir=legacy_data_dir,
        workspace_slug="personal",
        owner_email="owner@example.com",
        validate=True,
    ).run()
    user = User.objects.get(email="owner@example.com")
    client = APIClient()
    client.force_authenticate(user)
    return client, user


@pytest.mark.django_db(transaction=True)
def test_legacy_read_endpoints_are_served_from_sql(imported_api: tuple[APIClient, User]) -> None:
    client, _ = imported_api
    endpoints = {
        "/api/summary": dict,
        "/api/importers": list,
        "/api/net-worth-history": list,
        "/api/savings/accounts": list,
        "/api/savings/history": list,
        "/api/investments/accounts": list,
        "/api/investments/history": list,
        "/api/portfolio": list,
        "/api/portfolio-analysis": dict,
        "/api/real-estate": list,
        "/api/calculator": list,
        "/api/budget": list,
        "/api/fund-accounts": list,
        "/api/stock-accounts": list,
        "/api/crypto-accounts": list,
        "/api/funds": list,
        "/api/stocks": list,
        "/api/cryptos": list,
        "/api/orders": list,
        "/api/stock-orders": list,
        "/api/crypto-orders": list,
        "/api/fund-prices": list,
        "/api/stock-prices": list,
        "/api/crypto-prices": list,
        "/api/fund-analysis": list,
        "/api/stock-analysis": list,
        "/api/crypto-analysis": list,
        "/api/stock-splits": list,
    }
    for endpoint, response_type in endpoints.items():
        response = client.get(endpoint)
        assert response.status_code == 200, (endpoint, response.content)
        assert isinstance(response.json(), response_type)


@pytest.mark.django_db(transaction=True)
def test_real_estate_keeps_empty_expected_profit_for_client_fallback(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api

    projects = client.get("/api/real-estate").json()
    malaga = next(item for item in projects if item["nombre"] == "Synthetic project")

    assert malaga["beneficio_estimado"] is None


@pytest.mark.django_db(transaction=True)
def test_real_estate_preserves_multiple_dated_movements(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api

    response = client.post(
        "/api/real-estate",
        {
            "nombre": "Proyecto con amortizaciones",
            "plataforma": "WeCity",
            "estado": "Completado",
            "capital_inicial": 1500,
            "capital_nuevo": 1500,
            "beneficio_estimado": 100,
            "tir": 11,
            "meses": 18,
            "fecha_inicio": "2025-09-01",
            "fecha_vencimiento": "2027-03-01",
            "origen": "",
            "movimientos": [
                {
                    "tipo": "capital_return",
                    "fecha": "2026-06-22",
                    "importe": 970.96,
                    "nota": "Primera amortización",
                },
                {
                    "tipo": "capital_return",
                    "fecha": "2026-07-14",
                    "importe": 529.04,
                    "nota": "Amortización final",
                },
                {
                    "tipo": "profit",
                    "fecha": "2026-07-14",
                    "importe": 49.94,
                    "nota": "Intereses",
                },
            ],
        },
        format="json",
    )

    assert response.status_code == 201
    project = response.json()
    assert project["capital_devuelto"] == 1500
    assert project["beneficio_obtenido"] == 49.94
    assert project["beneficio_obtenido_neto"] == pytest.approx(40.4514)
    assert project["fecha_devolucion"] == "2026-07-14"
    assert [movement["nota"] for movement in project["movimientos"]] == [
        "Primera amortización",
        "Amortización final",
        "Intereses",
    ]
    assert project["movimientos"][-1]["retencion_irpf_aplicada"] == 19

    InstallationSettings.load().default_crowdfunding_tax_rate = Decimal("21.50")
    InstallationSettings.load().save(update_fields=("default_crowdfunding_tax_rate", "updated_at"))
    unchanged = next(
        item for item in client.get("/api/real-estate").json() if item["id"] == project["id"]
    )
    assert unchanged["beneficio_obtenido_neto"] == pytest.approx(40.4514)

    updated = client.put(
        f"/api/real-estate/{project['id']}",
        {
            "nombre": "Proyecto con amortizaciones",
            "plataforma": "WeCity",
            "estado": "Completado",
            "capital_inicial": 1500,
            "capital_nuevo": 1500,
            "beneficio_estimado": 100,
            "tir": 11,
            "meses": 18,
            "fecha_inicio": "2025-09-01",
            "fecha_vencimiento": "2027-03-01",
            "origen": "",
            "movimientos": [
                {
                    "id": movement["id"],
                    "tipo": movement["tipo"],
                    "fecha": movement["fecha"],
                    "importe": movement["importe"],
                    "nota": movement["nota"],
                }
                for movement in project["movimientos"]
            ],
        },
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["beneficio_obtenido_neto"] == pytest.approx(40.4514)

    history = {row["fecha"]: row for row in client.get("/api/net-worth-history").json()}
    assert history["2026-06"]["inversiones"] - history["2026-06"]["balances"] >= 529.04
    assert history["2026-07"]["inversiones"] - history["2026-07"]["balances"] >= 0


@pytest.mark.django_db(transaction=True)
def test_real_estate_persists_and_updates_custom_tax_rate(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api

    invalid_payload = {
        "nombre": "Proyecto inválido",
        "plataforma": "CrowdEstate",
        "estado": "Activo",
        "capital_inicial": 1000,
        "capital_nuevo": 1000,
        "beneficio_estimado": 120,
        "tir": 12,
        "meses": 12,
        "fecha_inicio": "2026-01-01",
        "fecha_vencimiento": "2027-01-01",
        "origen": "",
        "movimientos": [],
    }
    for value in (-1, 100.1, "invalid", "NaN"):
        response = client.post(
            "/api/real-estate",
            {**invalid_payload, "retencion_irpf": value},
            format="json",
        )
        assert response.status_code == 400
        assert "entre 0 y 100" in response.json()["error"]

    created = client.post(
        "/api/real-estate",
        {
            "nombre": "Proyecto Extranjero",
            "plataforma": "CrowdEstate",
            "estado": "Activo",
            "capital_inicial": 1000,
            "capital_nuevo": 1000,
            "beneficio_estimado": 120,
            "tir": 12,
            "meses": 12,
            "fecha_inicio": "2026-01-01",
            "fecha_vencimiento": "2027-01-01",
            "retencion_irpf": 0,
            "origen": "",
            "movimientos": [],
        },
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["retencion_irpf"] == 0

    project_id = created.json()["id"]
    updated = client.put(
        f"/api/real-estate/{project_id}",
        {
            "nombre": "Proyecto Extranjero Modificado",
            "plataforma": "CrowdEstate",
            "estado": "Activo",
            "capital_inicial": 1000,
            "capital_nuevo": 1000,
            "beneficio_estimado": 120,
            "tir": 12,
            "meses": 12,
            "fecha_inicio": "2026-01-01",
            "fecha_vencimiento": "2027-01-01",
            "retencion_irpf": 15.5,
            "origen": "",
            "movimientos": [],
        },
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["retencion_irpf"] == 15.5

    cleared = client.put(
        f"/api/real-estate/{project_id}",
        {
            "nombre": "Proyecto Extranjero Heredado",
            "plataforma": "CrowdEstate",
            "estado": "Activo",
            "capital_inicial": 1000,
            "capital_nuevo": 1000,
            "beneficio_estimado": 120,
            "tir": 12,
            "meses": 12,
            "fecha_inicio": "2026-01-01",
            "fecha_vencimiento": "2027-01-01",
            "retencion_irpf": None,
            "origen": "",
            "movimientos": [],
        },
        format="json",
    )
    assert cleared.status_code == 200
    assert cleared.json()["retencion_irpf"] is None


@pytest.mark.django_db(transaction=True)
def test_savings_account_can_be_edited(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api
    account = client.get("/api/savings/accounts").json()[0]

    response = client.put(
        f"/api/savings/accounts/{account['id']}",
        {
            "nombre": f"{account['nombre']} principal",
            "banco": account["banco"],
            "tipo": account["tipo"],
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["nombre"].endswith(" principal")


@pytest.mark.django_db(transaction=True)
def test_savings_snapshot_is_saved_on_last_day_of_month(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api
    account = client.get("/api/savings/accounts").json()[0]

    response = client.post(
        "/api/savings/history",
        {
            "fecha": "2028-02-01",
            "cuenta_id": account["id"],
            "saldo": 2500,
            "aporte": 100,
            "intereses": 4.5,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["fecha"] == "2028-02-29"


@pytest.mark.django_db(transaction=True)
def test_manual_investment_account_and_snapshot_can_be_updated(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api
    account = client.get("/api/investments/accounts").json()[0]

    edited = client.put(
        f"/api/investments/accounts/{account['id']}",
        {
            "nombre": f"{account['nombre']} manual",
            "plataforma": account["plataforma"],
            "tipo": account["tipo"],
        },
        format="json",
    )
    closed = client.post(
        "/api/investments/history",
        {
            "fecha": "2028-02-01",
            "cuenta_id": account["id"],
            "valor": 40000,
            "aporte": 500,
        },
        format="json",
    )

    assert edited.status_code == 200
    assert edited.json()["nombre"].endswith(" manual")
    assert closed.status_code == 201
    assert closed.json()["fecha"] == "2028-02-29"
    assert isinstance(closed.json()["intereses"], float)


@pytest.mark.django_db(transaction=True)
def test_portfolio_analysis_consolidates_positions_by_real_account(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api

    response = client.get("/api/portfolio-analysis")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == pytest.approx(
        sum(item["valor"] for item in payload["items"]),
        abs=0.01,
    )
    assert {"fund", "stock", "crypto", "real_estate"}.issubset(
        {item["origen"] for item in payload["items"]}
    )
    assert all(item["cuenta"] and item["plataforma"] for item in payload["items"])
    assert all(0 < item["peso"] <= 1 for item in payload["items"])
    fund_classes = {item["clase"] for item in payload["items"] if item["origen"] == "fund"}
    assert fund_classes == {"Renta variable"}


@pytest.mark.django_db(transaction=True)
def test_legacy_write_updates_postgresql_without_touching_csv(
    imported_api: tuple[APIClient, User],
    legacy_data_dir: Path,
) -> None:
    client, _ = imported_api
    csv_before = (legacy_data_dir / "savings_history.csv").read_bytes()

    response = client.post(
        "/api/savings/history",
        {"fecha": "2026-07-31", "cuenta_id": 1, "saldo": 1234.56, "aporte": 10},
        format="json",
    )

    assert response.status_code == 201
    assert AccountSnapshot.objects.get(
        date="2026-07-31",
        account__external_id="legacy:savings:1",
    ).value == Decimal("1234.56")
    assert (legacy_data_dir / "savings_history.csv").read_bytes() == csv_before


@pytest.mark.django_db(transaction=True)
def test_api_requires_authentication(imported_api: tuple[APIClient, User]) -> None:
    anonymous = APIClient()
    assert anonymous.get("/api/summary").status_code in {401, 403}


@pytest.mark.django_db(transaction=True)
def test_registered_parser_upload_is_persisted_and_deduplicated(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api
    content = (
        b"txid,pair,time,type,price,cost,fee,vol\n"
        b"new-tx,BTC/EUR,2026-07-20 12:00:00,buy,100000,100,1,0.001\n"
    )
    uploaded = SimpleUploadedFile("trades.csv", content, content_type="text/csv")

    response = client.post(
        "/api/crypto-orders/upload-kraken-pro",
        {"cuenta_id": "1", "file": uploaded},
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert Transaction.objects.filter(external_id="new-tx").exists()

    duplicate = SimpleUploadedFile("again.csv", content, content_type="text/csv")
    response = client.post(
        "/api/crypto-orders/upload-kraken-pro",
        {"cuenta_id": "1", "file": duplicate},
    )
    assert response.json()["duplicate"] is True


@pytest.mark.django_db(transaction=True)
def test_account_importer_is_required_compatible_and_drives_the_upload(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api

    missing = client.post(
        "/api/crypto-accounts",
        {"nombre": "Sin decidir", "plataforma": "Otro exchange"},
        format="json",
    )
    incompatible = client.post(
        "/api/crypto-accounts",
        {
            "nombre": "Importador incorrecto",
            "plataforma": "Otro exchange",
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
def test_crypto_chart_returns_ohlc_data(
    imported_api: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = imported_api
    monkeypatch.setattr(
        views,
        "yahoo_chart",
        lambda *_args, **_kwargs: (
            {"currency": "EUR"},
            [
                {
                    "fecha": "2026-07-20",
                    "precio": 70000,
                    "open": 69000,
                    "high": 71000,
                    "low": 68000,
                    "close": 70000,
                }
            ],
        ),
    )

    response = client.get("/api/crypto-chart/BTC?range=1m&interval=1d")

    assert response.status_code == 200
    assert response.json()["symbol"] == "BTC"
    assert response.json()["data"][0]["close"] == 70000


@pytest.mark.django_db(transaction=True)
def test_crypto_accounts_can_be_created_and_filter_orders(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api
    created = client.post(
        "/api/crypto-accounts",
        {
            "nombre": "Cuenta secundaria",
            "plataforma": "Otro exchange",
            "importer_slug": "none",
        },
        format="json",
    )

    assert created.status_code == 201
    account_id = created.json()["id"]
    assert created.json()["plataforma"] == "Otro exchange"

    source = Transaction.objects.filter(
        account__kind=Account.Kind.CRYPTO,
        instrument__kind="crypto",
    ).first()
    assert source is not None
    account = Account.objects.get(
        kind=Account.Kind.CRYPTO,
        external_id=f"legacy:crypto:{account_id}",
    )
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

    orders = client.get(f"/api/crypto-orders?cuenta_id={account_id}")
    analysis = client.get(f"/api/crypto-analysis?cuenta_id={account_id}")

    assert orders.status_code == 200
    assert [row["cuenta_id"] for row in orders.json()] == [account_id]
    assert orders.json()[0]["cuenta_nombre"] == "Cuenta secundaria"
    assert orders.json()[0]["plataforma"] == "Otro exchange"
    assert analysis.status_code == 200
    assert analysis.json()[0]["symbol"] == orders.json()[0]["symbol"]


@pytest.mark.django_db(transaction=True)
def test_fund_and_crypto_movements_can_be_created_and_edited_manually(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api
    fund_account = client.get("/api/fund-accounts").json()[0]
    fund = client.get("/api/funds").json()[0]

    created_fund = client.post(
        "/api/orders",
        {
            "cuenta_id": fund_account["id"],
            "isin": fund["isin"],
            "fecha_operacion": "2026-07-25",
            "fecha_liquidacion": "2026-07-26",
            "tipo_operacion": "SUSCRIPCION",
            "titulos": 2,
            "precio_neto": 50,
            "importe_neto": 100,
        },
        format="json",
    )

    assert created_fund.status_code == 201
    fund_id = created_fund.json()["operacion_id"]
    assert fund_id.startswith("manual:")
    updated_fund = client.put(
        f"/api/orders/{fund_id}",
        {
            "cuenta_id_original": fund_account["id"],
            "cuenta_id": fund_account["id"],
            "isin": fund["isin"],
            "fecha_operacion": "2026-07-25",
            "fecha_liquidacion": "2026-07-27",
            "tipo_operacion": "REEMBOLSO",
            "titulos": 1,
            "precio_neto": 55,
            "importe_neto": 55,
        },
        format="json",
    )
    assert updated_fund.status_code == 200
    assert updated_fund.json()["tipo_operacion"] == "REEMBOLSO"
    assert updated_fund.json()["importe_neto"] == 55

    crypto_account = client.get("/api/crypto-accounts").json()[0]
    crypto = client.get("/api/cryptos").json()[0]
    created_crypto = client.post(
        "/api/crypto-orders",
        {
            "cuenta_id": crypto_account["id"],
            "symbol": crypto["symbol"],
            "fecha_operacion": "2026-07-25",
            "tipo_operacion": "Compra",
            "titulos": 0.001,
            "precio_compra": 70000,
            "importe_neto": 70.5,
            "comision": 0.5,
        },
        format="json",
    )

    assert created_crypto.status_code == 201
    assert created_crypto.json()["tipo_operacion"] == "Compra"
    assert created_crypto.json()["comision"] == 0.5


@pytest.mark.django_db(transaction=True)
def test_stock_cashback_is_only_available_for_trade_republic(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api
    trade_republic = client.get("/api/stock-accounts").json()[0]
    stock = client.get("/api/stocks").json()[0]

    created = client.post(
        "/api/stock-orders",
        {
            "cuenta_id": trade_republic["id"],
            "isin": stock["isin"],
            "fecha_operacion": "2026-07-25",
            "tipo_operacion": "Compra",
            "titulos": 1,
            "precio_compra": 25,
            "importe_neto": 25,
            "comision": 0,
            "es_saveback": True,
        },
        format="json",
    )

    assert created.status_code == 201
    assert created.json()["es_saveback"] is True

    other_account = client.post(
        "/api/stock-accounts",
        {
            "nombre": "Broker secundario",
            "plataforma": "Otro broker",
            "importer_slug": "none",
        },
        format="json",
    ).json()
    rejected_cashback = client.post(
        "/api/stock-orders",
        {
            "cuenta_id": other_account["id"],
            "isin": stock["isin"],
            "fecha_operacion": "2026-07-25",
            "tipo_operacion": "Compra",
            "titulos": 1,
            "precio_compra": 25,
            "importe_neto": 25,
            "comision": 0,
            "es_saveback": True,
        },
        format="json",
    )

    assert rejected_cashback.status_code == 201
    assert rejected_cashback.json()["es_saveback"] is False

    regular = client.get(f"/api/stock-analysis?cuenta_id={trade_republic['id']}").json()
    cashback_as_benefit = client.get(
        f"/api/stock-analysis?cuenta_id={trade_republic['id']}&ignore_savebacks=true"
    ).json()
    regular_cost = sum(row["coste_total"] for row in regular)
    benefit_cost = sum(row["coste_total"] for row in cashback_as_benefit)
    assert benefit_cost < regular_cost


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("collection", "detail", "identifier_key", "identifier", "ticker"),
    [
        ("/api/stocks", "/api/stocks/US0378331005", "isin", "US0378331005", "AAPL"),
        ("/api/cryptos", "/api/cryptos/SOL", "symbol", "SOL", "SOL-EUR"),
    ],
)
def test_stock_and_crypto_assets_can_be_created_and_edit_their_ticker(
    imported_api: tuple[APIClient, User],
    collection: str,
    detail: str,
    identifier_key: str,
    identifier: str,
    ticker: str,
) -> None:
    client, _ = imported_api
    transaction_count = Transaction.objects.count()

    created = client.post(
        collection,
        {
            identifier_key: identifier,
            "nombre": "Activo manual",
            "ticker": ticker,
        },
        format="json",
    )

    assert created.status_code == 201
    assert created.json()[identifier_key] == identifier
    assert created.json()["ticker"] == ticker
    assert Transaction.objects.count() == transaction_count
    assert WorkspaceInstrument.objects.filter(
        instrument__identifiers__scheme=("crypto_symbol" if identifier_key == "symbol" else "isin"),
        instrument__identifiers__value=identifier,
    ).exists()
    assert any(row[identifier_key] == identifier for row in client.get(collection).json())

    updated = client.put(
        detail,
        {"nombre": "Activo editado", "ticker": f"{ticker}.EDIT"},
        format="json",
    )

    assert updated.status_code == 200
    assert updated.json()["nombre"] == "Activo editado"
    assert updated.json()["ticker"] == f"{ticker}.EDIT"


@pytest.mark.django_db(transaction=True)
def test_fund_performance_uses_market_history_and_filters_by_account(
    imported_api: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = imported_api
    cache.clear()
    created = client.post(
        "/api/fund-accounts",
        {
            "nombre": "Cuenta de prueba",
            "plataforma": "MyInvestor",
            "importer_slug": "fund_broker",
        },
        format="json",
    )
    account_id = created.json()["id"]
    account = Account.objects.get(
        kind=Account.Kind.FUNDS,
        external_id=f"legacy:funds:{account_id}",
    )
    source = Transaction.objects.filter(instrument__kind="fund").first()
    assert source is not None
    Transaction.objects.create(
        account=account,
        instrument=source.instrument,
        external_id="fund-performance-buy",
        trade_date="2026-01-01",
        operation_type=Transaction.OperationType.BUY,
        cash_flow_type=Transaction.CashFlowType.CONTRIBUTION,
        quantity=10,
        unit_price=10,
        net_amount=100,
        currency="EUR",
        provider_operation_type="SUSCRIPCION",
    )
    monkeypatch.setattr(
        views,
        "yahoo_chart",
        lambda *_args, **_kwargs: (
            {"currency": "EUR"},
            [
                {"fecha": "2026-01-01", "precio": 10},
                {"fecha": "2026-02-01", "precio": 12},
            ],
        ),
    )

    response = client.get(f"/api/account-performance?cuenta_id={account_id}&range=1y")

    assert response.status_code == 200
    assert response.json() == {
        "range": "1y",
        "cuenta_id": str(account_id),
        "data": [
            {
                "fecha": "2026-01-01",
                "valor": 100.0,
                "invertido": 100.0,
                "pnl": 0.0,
                "pnl_pct": 0.0,
            },
            {
                "fecha": "2026-02-01",
                "valor": 120.0,
                "invertido": 100.0,
                "pnl": 20.0,
                "pnl_pct": 20.0,
            },
        ],
    }

    analysis = client.get(f"/api/fund-analysis?cuenta_id={account_id}")
    orders = client.get(f"/api/orders?cuenta_id={account_id}")
    assert analysis.status_code == 200
    assert len(analysis.json()) == 1
    assert [row["cuenta_id"] for row in orders.json()] == [account_id]


@pytest.mark.django_db(transaction=True)
def test_fund_performance_rejects_an_incomplete_custom_range(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api
    response = client.get("/api/account-performance?cuenta_id=all&start=2026-01-01")
    assert response.status_code == 400
    assert response.json()["error"] == "Debes indicar fecha inicial y final"


@pytest.mark.django_db(transaction=True)
def test_price_refresh_endpoints_share_the_internal_handler(
    imported_api: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = imported_api
    monkeypatch.setattr(views, "yahoo_ticker", lambda _instrument: "TEST")
    monkeypatch.setattr(views, "quote_price", lambda _ticker: (100.0, "USD"))
    monkeypatch.setattr(
        views,
        "rate_to_base",
        lambda *_args, **_kwargs: FxConversion(Decimal("0.9"), date(2026, 1, 1), "test"),
    )

    for endpoint in (
        "/api/fund-prices/fetch",
        "/api/stock-prices/fetch",
        "/api/crypto-prices/fetch",
    ):
        response = client.post(endpoint, format="json")

        assert response.status_code == 200, (endpoint, response.content)
        assert response.json()["results"]
        assert all(item["precio"] == 90.0 for item in response.json()["results"])


@pytest.mark.django_db(transaction=True)
def test_stock_prices_and_analysis_use_only_the_latest_spot_quote(
    imported_api: tuple[APIClient, User],
) -> None:
    client, _ = imported_api
    transaction = (
        Transaction.objects.filter(instrument__kind="stock").select_related("instrument").first()
    )
    assert transaction is not None
    instrument = transaction.instrument
    isin = instrument.identifiers.get(scheme="isin").value
    MarketPrice.objects.create(
        instrument=instrument,
        quoted_at="2030-01-01T12:00:00Z",
        granularity=MarketPrice.Granularity.SPOT,
        close=Decimal("123.45"),
        currency="EUR",
        source="test-latest",
    )

    prices = client.get("/api/stock-prices")
    analysis = client.get("/api/stock-analysis")

    assert prices.status_code == 200
    matching_prices = [row for row in prices.json() if row["isin"] == isin]
    assert matching_prices == [
        {
            "isin": isin,
            "precio": 123.45,
            "updated": "2030-01-01",
            "moneda": "EUR",
            "moneda_base": "EUR",
            "precio_orig": 123.45,
            "tipo_cambio": 1.0,
            "fecha_tipo_cambio": "2030-01-01",
            "fuente_tipo_cambio": "identity",
            "fecha": "2030-01-01",
        }
    ]
    assert analysis.status_code == 200
    position = next(row for row in analysis.json() if row["isin"] == isin)
    assert position["precio_actual"] == 123.45
