from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from apps.accounts.models import Account, AccountSnapshot, FinancialProvider
from apps.api import views
from apps.common.models import InstallationSettings
from apps.imports.models import ImportBatch, ImportIssue
from apps.market_data.fx import FxConversion
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    MarketPrice,
    StockSplit,
    WorkspaceInstrument,
)
from apps.planning.models import BudgetLine
from apps.portfolio.models import ManualAsset
from apps.real_estate.models import RealEstateCashFlow, RealEstateInvestment
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.fixture
def api_context() -> tuple[APIClient, User]:
    workspace = Workspace.objects.create(
        name="Synthetic API",
        slug="personal",
        base_currency="EUR",
        timezone="Europe/Madrid",
    )
    user = User.objects.create_user(
        email="owner@example.com",
        password="synthetic-password",
    )
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=user,
        role=WorkspaceMembership.Role.OWNER,
    )
    InstallationSettings.load()

    savings = Account.objects.create(
        workspace=workspace,
        name="Synthetic savings",
        kind=Account.Kind.SAVINGS,
        subtype="Ahorro",
        provider_label="Demo Bank",
        currency="EUR",
        external_id="legacy:savings:1",
    )
    investment = Account.objects.create(
        workspace=workspace,
        name="Synthetic investment",
        kind=Account.Kind.MANUAL_INVESTMENT,
        subtype="Manual",
        provider_label="Demo Broker",
        currency="EUR",
        external_id="legacy:manual_investment:1",
    )
    funds = Account.objects.create(
        workspace=workspace,
        name="Synthetic funds",
        kind=Account.Kind.FUNDS,
        subtype="Renta Variable",
        provider_label="MyInvestor",
        importer_slug="fund_broker",
        currency="EUR",
        external_id="legacy:funds:1",
    )
    stocks = Account.objects.create(
        workspace=workspace,
        name="Synthetic stocks",
        kind=Account.Kind.STOCKS,
        subtype="Broker",
        provider_label="Trade Republic",
        importer_slug="trade_republic",
        currency="EUR",
        external_id="legacy:stocks:1",
    )
    crypto = Account.objects.create(
        workspace=workspace,
        name="Synthetic crypto",
        kind=Account.Kind.CRYPTO,
        provider_label="KrakenPro",
        importer_slug="kraken_spot",
        currency="EUR",
        external_id="legacy:crypto:1",
    )

    for account, value, contribution in (
        (savings, Decimal("1000"), Decimal("1000")),
        (investment, Decimal("500"), Decimal("500")),
    ):
        AccountSnapshot.objects.create(
            account=account,
            date=date(2026, 1, 31),
            value=value,
            contribution=contribution,
            earnings=Decimal("0"),
            currency="EUR",
            base_currency="EUR",
            base_value=value,
            base_contribution=contribution,
            base_earnings=Decimal("0"),
            fx_rate_to_base=Decimal("1"),
            fx_rate_date=date(2026, 1, 31),
            fx_source="identity",
        )

    fund = Instrument.objects.create(
        kind=Instrument.Kind.FUND,
        name="Synthetic Fund",
        quote_currency="EUR",
        metadata={"asset_class": "Renta variable", "subtype": "Global"},
    )
    stock = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="Synthetic Stock",
        quote_currency="EUR",
    )
    crypto_asset = Instrument.objects.create(
        kind=Instrument.Kind.CRYPTO,
        name="Synthetic Bitcoin",
        quote_currency="EUR",
    )
    for instrument, scheme, identifier_value in (
        (fund, InstrumentIdentifier.Scheme.ISIN, "SYNTH-FUND-001"),
        (stock, InstrumentIdentifier.Scheme.ISIN, "SYNTH-STOCK-001"),
        (crypto_asset, InstrumentIdentifier.Scheme.CRYPTO_SYMBOL, "BTC"),
    ):
        InstrumentIdentifier.objects.create(
            instrument=instrument,
            scheme=scheme,
            value=identifier_value,
            venue="",
            is_primary=True,
        )
    for instrument, ticker in (
        (fund, "SYNTH-FUND-EUR"),
        (stock, "SYNTH-STOCK-EUR"),
        (crypto_asset, "BTC-EUR"),
    ):
        InstrumentIdentifier.objects.create(
            instrument=instrument,
            scheme=InstrumentIdentifier.Scheme.YAHOO,
            value=ticker,
            venue="",
            is_primary=True,
        )
    for instrument in (fund, stock, crypto_asset):
        WorkspaceInstrument.objects.create(workspace=workspace, instrument=instrument)

    def buy_transaction(
        *,
        account: Account,
        instrument: Instrument,
        external_id: str,
        quantity: Decimal,
        unit_price: Decimal,
        trade_date: date,
        settlement_date: date | None,
        operation_type: str,
        cash_flow_type: str,
        provider_operation_type: str,
        name: str,
        market: str = "",
    ) -> None:
        fee = Decimal("0")
        Transaction.objects.create(
            account=account,
            instrument=instrument,
            external_id=external_id,
            trade_date=trade_date,
            settlement_date=settlement_date,
            operation_type=operation_type,
            cash_flow_type=cash_flow_type,
            quantity=quantity,
            unit_price=unit_price,
            net_amount=quantity * unit_price,
            fee=fee,
            currency="EUR",
            base_currency="EUR",
            base_unit_price=unit_price,
            base_net_amount=quantity * unit_price,
            base_fee=fee,
            fx_rate_to_base=Decimal("1"),
            fx_rate_date=settlement_date or trade_date,
            fx_source="identity",
            market=market,
            is_saveback=False,
            provider_operation_type=provider_operation_type,
            raw_metadata={"legacy_name": name},
        )

    buy_transaction(
        account=funds,
        instrument=fund,
        external_id="SYNTH-FUND-BUY-001",
        quantity=Decimal("10"),
        unit_price=Decimal("10"),
        trade_date=date(2026, 1, 15),
        settlement_date=date(2026, 1, 17),
        operation_type=Transaction.OperationType.BUY,
        cash_flow_type=Transaction.CashFlowType.CONTRIBUTION,
        provider_operation_type="SUSCRIPCION",
        name="Synthetic Fund",
        market="DEMO",
    )
    buy_transaction(
        account=stocks,
        instrument=stock,
        external_id="SYNTH-STOCK-BUY-001",
        quantity=Decimal("2"),
        unit_price=Decimal("50"),
        trade_date=date(2026, 1, 15),
        settlement_date=None,
        operation_type=Transaction.OperationType.BUY,
        cash_flow_type=Transaction.CashFlowType.NONE,
        provider_operation_type="Compra",
        name="Synthetic Stock",
    )
    buy_transaction(
        account=crypto,
        instrument=crypto_asset,
        external_id="SYNTH-CRYPTO-BUY-001",
        quantity=Decimal("5"),
        unit_price=Decimal("20"),
        trade_date=date(2026, 1, 15),
        settlement_date=None,
        operation_type=Transaction.OperationType.BUY,
        cash_flow_type=Transaction.CashFlowType.NONE,
        provider_operation_type="Compra",
        name="Synthetic Bitcoin",
    )

    quoted_at = datetime(2026, 1, 31, 12, tzinfo=UTC)
    for instrument, close in (
        (fund, Decimal("11")),
        (stock, Decimal("55")),
        (crypto_asset, Decimal("22")),
    ):
        MarketPrice.objects.create(
            instrument=instrument,
            quoted_at=quoted_at,
            granularity=MarketPrice.Granularity.SPOT,
            close=close,
            currency="EUR",
            source="synthetic-fixture",
        )
    StockSplit.objects.create(
        workspace=workspace,
        instrument=stock,
        effective_date=date(2025, 1, 1),
        ratio=Decimal("2"),
        source="Synthetic fixture",
    )

    project = RealEstateInvestment.objects.create(
        workspace=workspace,
        provider_label="Demo Platform",
        name="Synthetic project",
        status=RealEstateInvestment.Status.ACTIVE,
        start_date=date(2026, 1, 1),
        maturity_date=date(2027, 1, 1),
        expected_profit=None,
        expected_irr=Decimal("0.08"),
        expected_term_months=12,
        origin="Ahorro",
        currency="EUR",
    )
    RealEstateCashFlow.objects.create(
        investment=project,
        effective_date=date(2026, 1, 1),
        flow_type=RealEstateCashFlow.FlowType.CONTRIBUTION,
        amount=Decimal("1000"),
        is_external=True,
        source_note="Synthetic fixture",
    )
    ManualAsset.objects.create(
        workspace=workspace,
        provider_label="Manual",
        name="Synthetic cash",
        asset_class="Efectivo",
        subtype="Demo",
        value=Decimal("100"),
        currency="EUR",
        valued_at=date(2026, 1, 31),
    )
    BudgetLine.objects.create(
        workspace=workspace,
        category="Synthetic needs",
        amount=Decimal("100"),
        currency="EUR",
        line_type="Necesidad",
        sort_order=0,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    session = client.session
    session["active_workspace_id"] = str(workspace.pk)
    session.save()
    return client, user


@pytest.mark.django_db(transaction=True)
def test_read_endpoints_are_served_from_django_models(api_context: tuple[APIClient, User]) -> None:
    client, _ = api_context
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context

    projects = client.get("/api/real-estate").json()
    malaga = next(item for item in projects if item["name"] == "Synthetic project")

    assert malaga["expected_profit"] is None


@pytest.mark.django_db(transaction=True)
def test_real_estate_uses_uuid_and_native_fields(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context

    project = client.get("/api/real-estate").json()[0]

    UUID(project["id"])
    assert set(project) == {
        "id",
        "name",
        "platform",
        "status",
        "initial_capital",
        "new_capital",
        "returned_capital",
        "realized_profit",
        "net_realized_profit",
        "expected_profit",
        "net_expected_profit",
        "expected_irr_percent",
        "expected_term_months",
        "start_date",
        "maturity_date",
        "return_date",
        "movements",
        "origin",
        "tax_rate",
        "currency",
    }
    assert project["status"] == "active"
    delete_response = client.delete("/api/real-estate/1")
    assert delete_response.status_code == 404
    rejected = client.post(
        "/api/real-estate",
        {
            "nombre": "Legacy project",
            "fecha_inicio": "2026-01-01",
            "capital_inicial": 100,
        },
        format="json",
    )
    assert rejected.status_code == 400
    assert "non_field_errors" in rejected.json()["error"]


@pytest.mark.django_db(transaction=True)
def test_real_estate_preserves_multiple_dated_movements(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context

    response = client.post(
        "/api/real-estate",
        {
            "name": "Proyecto con amortizaciones",
            "platform": "WeCity",
            "status": "completed",
            "initial_capital": 1500,
            "new_capital": 1500,
            "expected_profit": 100,
            "expected_irr_percent": 11,
            "expected_term_months": 18,
            "start_date": "2025-09-01",
            "maturity_date": "2027-03-01",
            "origin": "",
            "movements": [
                {
                    "flow_type": "capital_return",
                    "effective_date": "2026-06-22",
                    "amount": 970.96,
                    "note": "Primera amortización",
                },
                {
                    "flow_type": "capital_return",
                    "effective_date": "2026-07-14",
                    "amount": 529.04,
                    "note": "Amortización final",
                },
                {
                    "flow_type": "profit",
                    "effective_date": "2026-07-14",
                    "amount": 49.94,
                    "note": "Intereses",
                },
            ],
        },
        format="json",
    )

    assert response.status_code == 201
    project = response.json()
    assert project["returned_capital"] == 1500
    assert project["realized_profit"] == 49.94
    assert project["net_realized_profit"] == pytest.approx(40.4514)
    assert project["return_date"] == "2026-07-14"
    assert [movement["note"] for movement in project["movements"]] == [
        "Primera amortización",
        "Amortización final",
        "Intereses",
    ]
    assert project["movements"][-1]["applied_tax_rate"] == 19

    InstallationSettings.load().default_crowdfunding_tax_rate = Decimal("21.50")
    InstallationSettings.load().save(update_fields=("default_crowdfunding_tax_rate", "updated_at"))
    unchanged = next(
        item for item in client.get("/api/real-estate").json() if item["id"] == project["id"]
    )
    assert unchanged["net_realized_profit"] == pytest.approx(40.4514)

    updated = client.put(
        f"/api/real-estate/{project['id']}",
        {
            "name": "Proyecto con amortizaciones",
            "platform": "WeCity",
            "status": "completed",
            "initial_capital": 1500,
            "new_capital": 1500,
            "expected_profit": 100,
            "expected_irr_percent": 11,
            "expected_term_months": 18,
            "start_date": "2025-09-01",
            "maturity_date": "2027-03-01",
            "origin": "",
            "movements": [
                {
                    "id": movement["id"],
                    "flow_type": movement["flow_type"],
                    "effective_date": movement["effective_date"],
                    "amount": movement["amount"],
                    "note": movement["note"],
                }
                for movement in project["movements"]
            ],
        },
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["net_realized_profit"] == pytest.approx(40.4514)

    history = {row["fecha"]: row for row in client.get("/api/net-worth-history").json()}
    assert history["2026-06"]["inversiones"] - history["2026-06"]["balances"] >= 529.04
    assert history["2026-07"]["inversiones"] - history["2026-07"]["balances"] >= 0


@pytest.mark.django_db(transaction=True)
def test_real_estate_persists_and_updates_custom_tax_rate(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context

    invalid_payload = {
        "name": "Proyecto inválido",
        "platform": "CrowdEstate",
        "status": "active",
        "initial_capital": 1000,
        "new_capital": 1000,
        "expected_profit": 120,
        "expected_irr_percent": 12,
        "expected_term_months": 12,
        "start_date": "2026-01-01",
        "maturity_date": "2027-01-01",
        "origin": "",
        "movements": [],
    }
    for value in (-1, 100.1, "invalid", "NaN"):
        response = client.post(
            "/api/real-estate",
            {**invalid_payload, "tax_rate": value},
            format="json",
        )
        assert response.status_code == 400
        assert "tax_rate" in response.json()["error"]

    created = client.post(
        "/api/real-estate",
        {
            "name": "Proyecto Extranjero",
            "platform": "CrowdEstate",
            "status": "active",
            "initial_capital": 1000,
            "new_capital": 1000,
            "expected_profit": 120,
            "expected_irr_percent": 12,
            "expected_term_months": 12,
            "start_date": "2026-01-01",
            "maturity_date": "2027-01-01",
            "tax_rate": 0,
            "origin": "",
            "movements": [],
        },
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["tax_rate"] == 0

    project_id = created.json()["id"]
    updated = client.put(
        f"/api/real-estate/{project_id}",
        {
            "name": "Proyecto Extranjero Modificado",
            "platform": "CrowdEstate",
            "status": "active",
            "initial_capital": 1000,
            "new_capital": 1000,
            "expected_profit": 120,
            "expected_irr_percent": 12,
            "expected_term_months": 12,
            "start_date": "2026-01-01",
            "maturity_date": "2027-01-01",
            "tax_rate": 15.5,
            "origin": "",
            "movements": [],
        },
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["tax_rate"] == 15.5

    cleared = client.put(
        f"/api/real-estate/{project_id}",
        {
            "name": "Proyecto Extranjero Heredado",
            "platform": "CrowdEstate",
            "status": "active",
            "initial_capital": 1000,
            "new_capital": 1000,
            "expected_profit": 120,
            "expected_irr_percent": 12,
            "expected_term_months": 12,
            "start_date": "2026-01-01",
            "maturity_date": "2027-01-01",
            "tax_rate": None,
            "origin": "",
            "movements": [],
        },
        format="json",
    )
    assert cleared.status_code == 200
    assert cleared.json()["tax_rate"] is None


@pytest.mark.django_db(transaction=True)
def test_savings_account_can_be_edited(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
    api_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = api_context
    monkeypatch.setattr(
        views,
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
def test_workspace_export_includes_legacy_and_native_savings_rows(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    native = client.post(
        "/api/savings/accounts",
        {"name": "Native export savings", "bank": "Bank", "type": "Cash"},
        format="json",
    ).json()
    client.post(
        "/api/savings/history",
        {"account_id": native["id"], "date": "2026-02-01", "balance": 200},
        format="json",
    )
    archived = client.post(
        "/api/savings/accounts",
        {"name": "Archived export savings", "bank": "Bank", "type": "Cash"},
        format="json",
    ).json()
    client.post(
        "/api/savings/history",
        {"account_id": archived["id"], "date": "2026-03-01", "balance": 321},
        format="json",
    )
    Account.objects.filter(pk=archived["id"]).update(archived_at=timezone.now())
    native_investment = client.post(
        "/api/investments/accounts",
        {"name": "Native export investment", "platform": "Broker", "type": "Managed"},
        format="json",
    ).json()
    client.post(
        "/api/investments/history",
        {
            "account_id": native_investment["id"],
            "date": "2026-02-01",
            "value": 700,
            "contribution": 100,
            "interest": 10,
        },
        format="json",
    )
    archived_investment = client.post(
        "/api/investments/accounts",
        {"name": "Archived export investment", "platform": "Broker", "type": "Managed"},
        format="json",
    ).json()
    client.post(
        "/api/investments/history",
        {
            "account_id": archived_investment["id"],
            "date": "2026-03-01",
            "value": 321,
            "contribution": 20,
            "interest": -2,
        },
        format="json",
    )
    Account.objects.filter(pk=archived_investment["id"]).update(archived_at=timezone.now())
    exported = client.get("/api/account/export")

    assert exported.status_code == 200
    data = exported.json()
    assert data["format"] == "finanzr-workspace-v2"
    assert {item["name"] for item in data["savings_accounts"]} == {
        "Native export savings",
        "Archived export savings",
        "Synthetic savings",
    }
    assert all(
        set(item) == {"id", "name", "bank", "type", "currency"} for item in data["savings_accounts"]
    )
    assert {item["account_id"] for item in data["savings_history"]} == {
        native["id"],
        archived["id"],
        str(Account.objects.get(external_id="legacy:savings:1").id),
    }
    assert {item["account_id"]: item["balance_original"] for item in data["savings_history"]} == {
        native["id"]: 200,
        archived["id"]: 321,
        str(Account.objects.get(external_id="legacy:savings:1").id): 1000,
    }
    assert all(
        set(item)
        == {
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
        for item in data["savings_history"]
    )
    investment_legacy = Account.objects.get(external_id="legacy:manual_investment:1")
    assert {item["name"] for item in data["investment_accounts"]} == {
        "Synthetic investment",
        "Native export investment",
        "Archived export investment",
    }
    assert all(
        set(item) == {"id", "name", "platform", "type", "currency"}
        for item in data["investment_accounts"]
    )
    assert {item["account_id"] for item in data["investment_history"]} == {
        str(investment_legacy.id),
        native_investment["id"],
        archived_investment["id"],
    }
    assert {item["account_id"]: item["value_original"] for item in data["investment_history"]} == {
        str(investment_legacy.id): 500,
        native_investment["id"]: 700,
        archived_investment["id"]: 321,
    }
    assert all(
        set(item)
        == {
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
        for item in data["investment_history"]
    )
    assert client.get("/api/summary").json()["total_investments"] == 1521
    assert client.get("/api/summary").json()["total_savings"] == 1521


@pytest.mark.django_db(transaction=True)
def test_manual_investment_account_and_snapshot_can_be_updated(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
    api_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = api_context
    monkeypatch.setattr(
        views,
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
def test_portfolio_native_contract_uses_uuid_and_english_fields(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    seeded_asset = ManualAsset.objects.get(name="Synthetic cash")
    assert (
        client.patch(
            "/api/auth/preferences", {"summary_sources": ["manual_assets"]}, format="json"
        ).status_code
        == 200
    )
    before = client.get("/api/summary").json()
    listed = client.get("/api/portfolio")

    assert listed.status_code == 200
    assert listed.json() == [
        {
            "id": str(seeded_asset.id),
            "name": "Synthetic cash",
            "asset_class": "Efectivo",
            "subtype": "Demo",
            "platform": "Manual",
            "value": 100,
            "currency": "EUR",
        }
    ]
    assert client.get("/api/portfolio/1").status_code == 404

    created = client.post(
        "/api/portfolio",
        {
            "name": "Native reserve",
            "asset_class": "Cash",
            "subtype": "Liquid",
            "platform": "Synthetic bank",
            "value": "1234.56789012",
        },
        format="json",
    )

    assert created.status_code == 201
    native = created.json()
    UUID(native["id"])
    assert native["name"] == "Native reserve"
    assert native["asset_class"] == "Cash"
    assert native["subtype"] == "Liquid"
    assert native["platform"] == "Synthetic bank"
    assert native["value"] == pytest.approx(1234.56789012)
    assert native["currency"] == "EUR"
    stored = ManualAsset.objects.get(pk=native["id"])
    assert stored.id == UUID(native["id"])
    after = client.get("/api/summary").json()
    assert after["net_worth"] == pytest.approx(before["net_worth"] + 1234.57)

    updated = client.put(
        f"/api/portfolio/{stored.id}",
        {"value": "1300.00000001"},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == str(stored.id)
    assert updated.json()["value"] == pytest.approx(1300.00000001)


@pytest.mark.django_db(transaction=True)
def test_portfolio_native_contract_resolves_and_clears_providers(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    provider = FinancialProvider.objects.create(
        slug="canonical-bank",
        name="Canonical Bank",
        provider_type=FinancialProvider.ProviderType.BANK,
    )
    created = client.post(
        "/api/portfolio",
        {
            "name": "Linked reserve",
            "asset_class": "Cash",
            "platform": "canonical bank",
            "value": 100,
        },
        format="json",
    )

    assert created.status_code == 201
    asset = ManualAsset.objects.get(pk=created.json()["id"])
    assert asset.provider_id == provider.id
    assert asset.provider_label == ""
    assert created.json()["platform"] == "Canonical Bank"

    renamed_asset = client.put(
        f"/api/portfolio/{asset.id}",
        {"name": "Renamed linked reserve"},
        format="json",
    )
    assert renamed_asset.status_code == 200
    asset.refresh_from_db()
    assert asset.provider_id == provider.id
    assert asset.provider_label == ""
    assert renamed_asset.json()["platform"] == "Canonical Bank"

    renamed = client.put(
        f"/api/portfolio/{asset.id}",
        {"platform": "Personal label"},
        format="json",
    )
    assert renamed.status_code == 200
    asset.refresh_from_db()
    assert asset.provider_id is None
    assert asset.provider_label == "Personal label"
    assert renamed.json()["platform"] == "Personal label"

    relinked = client.put(
        f"/api/portfolio/{asset.id}",
        {"platform": "CANONICAL BANK"},
        format="json",
    )
    assert relinked.status_code == 200
    asset.refresh_from_db()
    assert asset.provider_id == provider.id
    assert asset.provider_label == ""
    assert relinked.json()["platform"] == "Canonical Bank"

    cleared = client.put(
        f"/api/portfolio/{asset.id}",
        {"platform": ""},
        format="json",
    )
    assert cleared.status_code == 200
    asset.refresh_from_db()
    assert asset.provider_id is None
    assert asset.provider_label == ""
    assert cleared.json()["platform"] == ""
    exported = client.get("/api/account/export")
    assert exported.status_code == 200
    assert (
        next(row for row in exported.json()["portfolio"] if row["id"] == str(asset.id))["platform"]
        == ""
    )


@pytest.mark.django_db(transaction=True)
def test_portfolio_native_contract_rejects_legacy_fields_and_model_overflows(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    asset_id = client.get("/api/portfolio").json()[0]["id"]
    legacy_payload = {
        "nombre": "Rejected",
        "tipo_renta": "Cash",
        "efectivo": 100,
    }
    assert client.post("/api/portfolio", legacy_payload, format="json").status_code == 400
    assert (
        client.post(
            "/api/portfolio",
            {"name": "Valid", "asset_class": "Cash", "value": 100, "unknown": True},
            format="json",
        ).status_code
        == 400
    )

    for field, value in (
        ("name", "N" * 201),
        ("asset_class", "C" * 81),
        ("subtype", "S" * 121),
        ("platform", "P" * 161),
    ):
        assert (
            client.post(
                "/api/portfolio",
                {"name": "Valid", "asset_class": "Cash", "value": 100, field: value},
                format="json",
            ).status_code
            == 400
        )
        assert (
            client.put(f"/api/portfolio/{asset_id}", {field: value}, format="json").status_code
            == 400
        )


@pytest.mark.django_db(transaction=True)
def test_portfolio_native_contract_isolates_uuid_scope_and_types(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    savings_id = Account.objects.get(kind=Account.Kind.SAVINGS).id
    foreign_workspace = Workspace.objects.create(
        name="Foreign portfolio workspace", slug="foreign-portfolio", base_currency="EUR"
    )
    foreign_asset = ManualAsset.objects.create(
        workspace=foreign_workspace,
        name="Foreign asset",
        asset_class="Cash",
        value=Decimal("50"),
        currency="EUR",
        valued_at=date(2028, 1, 31),
    )

    assert client.get("/api/portfolio/not-a-uuid").status_code == 404
    assert client.get("/api/portfolio/1").status_code == 404
    put_numeric_id = client.put("/api/portfolio/1", {}, format="json")
    assert put_numeric_id.status_code == 404
    deleted_numeric_id = client.delete("/api/portfolio/1")
    assert deleted_numeric_id.status_code == 404
    put_invalid_uuid = client.put("/api/portfolio/not-a-uuid", {}, format="json")
    assert put_invalid_uuid.status_code == 404
    put_savings_id = client.put(
        f"/api/portfolio/{savings_id}",
        {"name": "Wrong type"},
        format="json",
    )
    assert put_savings_id.status_code == 404
    put_foreign_asset = client.put(
        f"/api/portfolio/{foreign_asset.id}",
        {"name": "Should remain hidden"},
        format="json",
    )
    assert put_foreign_asset.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_portfolio_export_includes_seeded_native_and_archived_assets(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    seeded_asset = ManualAsset.objects.get(name="Synthetic cash")
    native = client.post(
        "/api/portfolio",
        {
            "name": "Native export reserve",
            "asset_class": "Cash",
            "subtype": "Liquid",
            "platform": "Synthetic bank",
            "value": "1234.56789012",
        },
        format="json",
    ).json()
    archived = ManualAsset.objects.create(
        workspace=seeded_asset.workspace,
        name="Archived export asset",
        asset_class="Property",
        subtype="Private",
        provider_label="Synthetic platform",
        value=Decimal("765.43000001"),
        currency="EUR",
        valued_at=date(2028, 2, 29),
        archived_at=timezone.now(),
    )

    before = client.get("/api/summary").json()
    exported = client.get("/api/account/export")

    assert exported.status_code == 200
    data = exported.json()
    assert data["format"] == "finanzr-workspace-v2"
    rows = {item["id"]: item for item in data["portfolio"]}
    assert set(rows) == {str(seeded_asset.id), native["id"], str(archived.id)}
    assert rows[str(seeded_asset.id)] == {
        "id": str(seeded_asset.id),
        "name": "Synthetic cash",
        "asset_class": "Efectivo",
        "subtype": "Demo",
        "platform": "Manual",
        "value": 100,
        "currency": "EUR",
    }
    assert rows[native["id"]]["value"] == pytest.approx(1234.56789012)
    assert rows[str(archived.id)] == {
        "id": str(archived.id),
        "name": "Archived export asset",
        "asset_class": "Property",
        "subtype": "Private",
        "platform": "Synthetic platform",
        "value": pytest.approx(765.43000001),
        "currency": "EUR",
    }
    assert data["summary"] == before
    assert all(
        set(item) == {"id", "name", "asset_class", "subtype", "platform", "value", "currency"}
        for item in data["portfolio"]
    )


@pytest.mark.django_db(transaction=True)
def test_traded_account_export_includes_legacy_native_and_archived_rows(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    legacy = Account.objects.get(kind=Account.Kind.FUNDS)
    native = client.post(
        "/api/fund-accounts",
        {
            "name": "Native traded export",
            "platform": "Synthetic broker",
            "type": "Managed",
            "currency": "EUR",
            "importer_slug": "none",
        },
        format="json",
    ).json()
    archived = Account.objects.create(
        workspace=legacy.workspace,
        name="Archived traded export",
        kind=Account.Kind.FUNDS,
        provider_label="Archived broker",
        currency="EUR",
        archived_at=timezone.now(),
    )

    exported = client.get("/api/account/export")

    assert exported.status_code == 200
    rows = {row["id"]: row for row in exported.json()["fund_accounts"]}
    assert {str(legacy.id), native["id"], str(archived.id)} <= set(rows)
    assert all(
        set(row) == {"id", "name", "platform", "type", "currency", "importer_slug", "importer_name"}
        for row in rows.values()
    )
    assert rows[native["id"]]["id"] == native["id"]
    assert rows[str(archived.id)]["name"] == "Archived traded export"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "endpoint",
    ("/api/fund-accounts", "/api/stock-accounts", "/api/crypto-accounts"),
)
def test_traded_account_crud_uses_strict_native_contract(
    api_context: tuple[APIClient, User], endpoint: str
) -> None:
    client, _ = api_context
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
def test_portfolio_analysis_consolidates_positions_by_real_account(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context

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
    manual = next(item for item in payload["items"] if item["origen"] == "manual")
    manual_asset = ManualAsset.objects.get(name="Synthetic cash")
    assert manual["id"] == f"manual:{manual_asset.id}"
    assert manual["cuenta_id"] == f"manual:{manual_asset.id}"
    account_kinds = {
        "fund": Account.Kind.FUNDS,
        "stock": Account.Kind.STOCKS,
        "crypto": Account.Kind.CRYPTO,
    }
    for item in payload["items"]:
        if item["origen"] not in account_kinds:
            continue
        prefix = f"{item['origen']}:"
        account_id = item["cuenta_id"].removeprefix(prefix)
        UUID(account_id)
        assert item["id"].startswith(f"{item['cuenta_id']}:")
        assert Account.objects.filter(pk=account_id, kind=account_kinds[item["origen"]]).exists()


@pytest.mark.django_db(transaction=True)
def test_savings_write_persists_to_database(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context

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
def test_api_requires_authentication(api_context: tuple[APIClient, User]) -> None:
    anonymous = APIClient()
    assert anonymous.get("/api/summary").status_code in {401, 403}


@pytest.mark.django_db(transaction=True)
def test_registered_parser_upload_is_persisted_and_deduplicated(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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

    duplicate = SimpleUploadedFile("again.csv", content, content_type="text/csv")
    response = client.post(
        "/api/crypto-orders/upload-kraken-pro",
        {"account_id": str(Account.objects.get(kind=Account.Kind.CRYPTO).id), "file": duplicate},
    )
    assert response.json()["duplicate"] is True


@pytest.mark.django_db(transaction=True)
def test_account_importer_is_required_compatible_and_drives_the_upload(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context

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
def test_traded_account_delete_removes_import_dependents_atomically(
    api_context: tuple[APIClient, User],
) -> None:
    client, user = api_context
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
            "fecha_operacion": "2026-07-22",
            "tipo_operacion": "Compra",
            "titulos": "0.001",
            "precio_compra": "100000",
            "importe_neto": "101",
            "comision": "1",
            "divisa": "EUR",
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
def test_transaction_detail_is_scoped_by_uuid_and_workspace_kind(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
        "fecha_operacion": "2026-02-02",
        "tipo_operacion": "Compra",
        "titulos": "1",
        "precio_compra": "10",
        "importe_neto": "10",
        "comision": "0",
        "divisa": "EUR",
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
            "fecha_operacion": "2026-02-02",
            "tipo_operacion": "Compra",
            "titulos": "1",
            "precio_compra": "10",
            "importe_neto": "10",
            "comision": "0",
            "divisa": "EUR",
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
def test_transaction_move_handles_raced_external_id_conflict_atomically(
    api_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = api_context
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
            "fecha_operacion": "2026-02-03",
            "tipo_operacion": "Compra",
            "titulos": "2",
            "precio_compra": "11",
            "importe_neto": "22",
            "comision": "0",
            "divisa": "EUR",
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
    api_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = api_context
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
                "fecha_operacion": "2026-02-04",
                "tipo_operacion": "Compra",
                "titulos": "3",
                "precio_compra": "12",
                "importe_neto": "36",
                "comision": "0",
                "divisa": "EUR",
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
    api_context: tuple[APIClient, User],
) -> None:
    client, user = api_context
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
        ("/api/orders", Account.Kind.FUNDS, "isin", "SYNTH-FUND-001", "precio_neto", "SUSCRIPCION"),
        (
            "/api/stock-orders",
            Account.Kind.STOCKS,
            "isin",
            "SYNTH-STOCK-001",
            "precio_compra",
            "Compra",
        ),
        ("/api/crypto-orders", Account.Kind.CRYPTO, "symbol", "BTC", "precio_compra", "Compra"),
    ),
)
def test_manual_traded_transactions_validate_native_typed_contract(
    api_context: tuple[APIClient, User],
    endpoint: str,
    account_kind: str,
    asset_key: str,
    asset_value: str,
    price_key: str,
    operation: str,
) -> None:
    client, _ = api_context
    account = Account.objects.get(kind=account_kind)
    payload = {
        "account_id": str(account.id),
        asset_key: asset_value,
        "fecha_operacion": "2026-07-25",
        "tipo_operacion": operation,
        "titulos": "2.5",
        price_key: "40",
        "importe_neto": "100",
        "comision": "0.5",
        "divisa": "EUR",
        "es_saveback": True,
        "tipo_cambio": "1",
        "fecha_tipo_cambio": "2026-07-25",
        "fuente_tipo_cambio": "identity",
        "mercado": "Synthetic market",
    }
    if account_kind == Account.Kind.FUNDS:
        payload["fecha_liquidacion"] = ""

    created = client.post(endpoint, payload, format="json")

    assert created.status_code == 201, created.content
    transaction_row = Transaction.objects.get(pk=created.json()["id"])
    assert "operacion_id" not in created.json()
    assert transaction_row.external_id is None
    assert transaction_row.account_id == account.id
    assert transaction_row.market == "Synthetic market"
    assert transaction_row.fx_rate_to_base == Decimal("1")
    if account_kind == Account.Kind.FUNDS:
        assert transaction_row.settlement_date is None

    for invalid_field, invalid_value in (
        ("unknown", "rejected"),
        ("cuenta_id", "1"),
        ("cuenta_id_original", "1"),
    ):
        invalid = {**payload, invalid_field: invalid_value}
        rejected = client.post(endpoint, invalid, format="json")
        assert rejected.status_code == 400, (invalid_field, rejected.content)


@pytest.mark.django_db(transaction=True)
def test_upload_contract_distinguishes_direct_and_account_bound_multipart(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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


@pytest.mark.django_db(transaction=True)
def test_traded_account_scope_and_roles_cover_archived_foreign_and_viewer_rows(
    api_context: tuple[APIClient, User],
) -> None:
    client, user = api_context
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
def test_crypto_chart_returns_ohlc_data(
    api_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = api_context
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
    assert [row["cuenta_id"] for row in orders.json()] == [account_id]
    assert orders.json()[0]["cuenta_nombre"] == "Cuenta secundaria"
    assert orders.json()[0]["plataforma"] == "Otro exchange"
    assert analysis.status_code == 200
    assert analysis.json()[0]["symbol"] == orders.json()[0]["symbol"]


@pytest.mark.django_db(transaction=True)
def test_fund_and_crypto_movements_can_be_created_and_edited_manually(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    fund_account = client.get("/api/fund-accounts").json()[0]
    fund = client.get("/api/funds").json()[0]

    created_fund = client.post(
        "/api/orders",
        {
            "account_id": fund_account["id"],
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
    fund_id = created_fund.json()["id"]
    assert UUID(fund_id)
    assert Transaction.objects.get(pk=fund_id).external_id is None
    updated_fund = client.put(
        f"/api/orders/{fund_id}",
        {
            "account_id": fund_account["id"],
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
            "account_id": crypto_account["id"],
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    trade_republic = client.get("/api/stock-accounts").json()[0]
    stock = client.get("/api/stocks").json()[0]

    created = client.post(
        "/api/stock-orders",
        {
            "account_id": trade_republic["id"],
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

    regular = client.get(f"/api/stock-analysis?account_id={trade_republic['id']}").json()
    cashback_as_benefit = client.get(
        f"/api/stock-analysis?account_id={trade_republic['id']}&ignore_savebacks=true"
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
    api_context: tuple[APIClient, User],
    collection: str,
    detail: str,
    identifier_key: str,
    identifier: str,
    ticker: str,
) -> None:
    client, _ = api_context
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
    api_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = api_context
    cache.clear()
    created = client.post(
        "/api/fund-accounts",
        {
            "name": "Cuenta de prueba",
            "platform": "MyInvestor",
            "importer_slug": "fund_broker",
        },
        format="json",
    )
    account_id = created.json()["id"]
    account = Account.objects.get(pk=account_id)
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

    response = client.get(f"/api/investment-performance/fund?account_id={account_id}&range=1y")

    assert response.status_code == 200
    assert response.json() == {
        "range": "1y",
        "account_id": str(account_id),
        "kind": "fund",
        "moneda_base": "EUR",
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

    analysis = client.get(f"/api/fund-analysis?account_id={account_id}")
    orders = client.get(f"/api/orders?account_id={account_id}")
    assert analysis.status_code == 200
    assert len(analysis.json()) == 1
    assert [row["cuenta_id"] for row in orders.json()] == [account_id]


@pytest.mark.django_db(transaction=True)
def test_fund_performance_rejects_an_incomplete_custom_range(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    response = client.get("/api/investment-performance/fund?account_id=all&start=2026-01-01")
    assert response.status_code == 400
    assert response.json()["error"] == "Debes indicar fecha inicial y final"


@pytest.mark.django_db(transaction=True)
def test_price_refresh_endpoints_share_the_internal_handler(
    api_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = api_context
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
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
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
