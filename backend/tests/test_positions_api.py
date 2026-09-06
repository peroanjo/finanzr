from decimal import Decimal
from uuid import UUID

import pytest
from apps.accounts.models import Account
from apps.api.position_projection import PositionProjectionError, native_position_rows
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    WorkspaceInstrument,
)
from apps.portfolio.models import ManualAsset
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace
from rest_framework.test import APIClient


@pytest.mark.django_db(transaction=True)
def test_analysis_endpoints_expose_only_the_native_position_contract(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    common = {
        "instrument_id",
        "kind",
        "name",
        "quantity",
        "cost",
        "current_price",
        "current_value",
        "unrealized_pnl",
        "realized_pnl",
        "currency",
        "base_currency",
    }
    expected = {
        "/api/fund-analysis": common
        | {"asset_class", "subtype", "average_price", "return_percent"},
        "/api/stock-analysis": common,
        "/api/crypto-analysis": common,
    }
    for endpoint, keys in expected.items():
        response = client.get(endpoint)
        assert response.status_code == 200, (endpoint, response.content)
        payload = response.json()
        rows = payload["positions"] if endpoint == "/api/fund-analysis" else payload
        for row in rows:
            assert set(row) == keys
            UUID(row["instrument_id"])
            assert row["kind"] in {"fund", "stock", "crypto"}
            assert not {
                "isin",
                "symbol",
                "nombre",
                "titulos",
                "participaciones",
                "precio_actual",
                "valor_actual",
                "pnl",
                "pnl_realizada",
                "moneda",
            } & set(row)


@pytest.mark.django_db(transaction=True)
def test_fund_analysis_exposes_authoritative_realized_pnl_by_account_scope(
    traded_context: tuple[APIClient, User],
) -> None:
    client, user = traded_context
    workspace = user.memberships.get().workspace
    account_one = Account.objects.get(kind=Account.Kind.FUNDS)
    account_two = Account.objects.create(
        workspace=workspace,
        name="Synthetic second fund account",
        kind=Account.Kind.FUNDS,
        currency="EUR",
    )
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.FUND,
        name="Synthetic aggregate fund",
        quote_currency="EUR",
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value="SYNTH-AGGREGATE-001",
        venue="",
        is_primary=True,
    )
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=instrument)

    def add_order(
        account: Account,
        operation_type: str,
        quantity: str,
        net_amount: str,
        base_net_amount: str | None,
    ) -> None:
        Transaction.objects.create(
            account=account,
            instrument=instrument,
            trade_date="2026-03-01",
            operation_type=operation_type,
            cash_flow_type=Transaction.CashFlowType.NONE,
            quantity=quantity,
            unit_price=net_amount,
            net_amount=net_amount,
            fee=0,
            currency="EUR",
            base_currency="EUR",
            base_net_amount=base_net_amount,
            base_unit_price=base_net_amount,
            base_fee=0,
        )

    add_order(account_one, Transaction.OperationType.BUY, "10", "100", "100")
    add_order(account_one, Transaction.OperationType.SELL, "4", "60", "60")
    add_order(account_one, Transaction.OperationType.BUY, "2", "30", None)
    add_order(account_one, Transaction.OperationType.SELL, "3", "51", "51")
    add_order(account_two, Transaction.OperationType.TRANSFER_IN, "5", "50", "50")
    add_order(account_two, Transaction.OperationType.TRANSFER_OUT, "5", "65", "65")

    baseline_all_accounts = client.get("/api/fund-analysis?account_id=all")
    assert baseline_all_accounts.status_code == 200

    foreign_workspace = Workspace.objects.create(
        name="Synthetic foreign fund workspace",
        slug="synthetic-foreign-fund",
        base_currency="EUR",
    )
    foreign_account = Account.objects.create(
        workspace=foreign_workspace,
        name="Synthetic foreign fund account",
        kind=Account.Kind.FUNDS,
        currency="EUR",
    )
    add_order(foreign_account, Transaction.OperationType.BUY, "100", "100", "100")
    add_order(foreign_account, Transaction.OperationType.SELL, "100", "1000", "1000")

    all_accounts = client.get("/api/fund-analysis?account_id=all")
    first_account = client.get(f"/api/fund-analysis?account_id={account_one.id}")
    second_account = client.get(f"/api/fund-analysis?account_id={account_two.id}")

    assert all_accounts.status_code == 200
    assert first_account.status_code == 200
    assert second_account.status_code == 200
    assert all_accounts.json()["base_currency"] == "EUR"
    assert all_accounts.json()["realized_pnl"] == pytest.approx(
        baseline_all_accounts.json()["realized_pnl"]
    )
    assert all_accounts.json()["realized_pnl"] == pytest.approx(48.9411764706)
    assert first_account.json()["realized_pnl"] == pytest.approx(35.1666666667)
    assert second_account.json()["realized_pnl"] == pytest.approx(15)
    assert not any(
        row["instrument_id"] == str(instrument.id) for row in second_account.json()["positions"]
    )
    assert any(
        row["instrument_id"] == str(instrument.id) for row in all_accounts.json()["positions"]
    )


def test_native_position_projection_fails_loudly_for_an_orphan() -> None:
    with pytest.raises(PositionProjectionError, match="ORPHAN"):
        native_position_rows(
            [{"isin": "ORPHAN", "nombre": "Orphan", "titulos": 1}],
            [],
            kind="stock",
            base_currency="EUR",
        )


@pytest.mark.django_db(transaction=True)
def test_native_position_projection_uses_visible_instrument_name(
    traded_context: tuple[APIClient, User],
) -> None:
    instrument = Instrument.objects.get(name="Synthetic Stock")
    isin = instrument.identifiers.get(scheme=InstrumentIdentifier.Scheme.ISIN).value

    rows = native_position_rows(
        [
            {
                "isin": isin,
                "nombre": "Legacy calculation label",
                "titulos": Decimal("1"),
                "coste_total": Decimal("10"),
                "precio_actual": None,
                "valor_actual": None,
                "pnl": None,
                "pnl_realizada": Decimal("0"),
                "moneda": "USD",
            }
        ],
        [instrument],
        kind=Instrument.Kind.STOCK,
        base_currency="EUR",
    )

    assert rows[0]["name"] == instrument.name
    assert rows[0]["name"] != "Legacy calculation label"
    assert rows[0]["currency"] == "USD"
    assert rows[0]["base_currency"] == "EUR"


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
