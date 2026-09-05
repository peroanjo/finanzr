from datetime import date
from decimal import Decimal

import pytest
from apps.accounts.models import Account
from apps.api import market_queries
from apps.market_data.fx import CurrencyConversionError, FxConversion
from apps.portfolio.models import ManualAsset
from apps.users.models import User
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


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
    assert data["format"] == "finanzr-workspace-v4"
    for section in ("funds", "stocks", "cryptos"):
        assert all(
            set(item)
            == {
                "id",
                "kind",
                "name",
                "quote_currency",
                "identifiers",
                "asset_class",
                "subtype",
                "is_active",
            }
            for item in data[section]
        )
        assert all("metadata" not in item and "legacy_id" not in item for item in data[section])
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
    assert data["format"] == "finanzr-workspace-v4"
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
    exported_orders = exported.json()["orders"]
    assert exported_orders
    assert all(
        not {
            "external_id",
            "raw_metadata",
            "import_batch",
            "operacion_id",
            "fecha_operacion",
            "tipo_operacion",
        }
        & set(order)
        for order in exported_orders
    )


@pytest.mark.parametrize("selection", ["all", "invalid", "legacy", "missing", "fund"])
def test_export_sections_preserve_native_reads_and_account_filter_errors(
    api_context: tuple[APIClient, User], selection: str
) -> None:
    client, _ = api_context
    if selection == "legacy":
        query = "?cuenta_id=1"
    elif selection == "missing":
        query = "?account_id=00000000-0000-0000-0000-000000000000"
    elif selection == "fund":
        account = Account.objects.get(external_id="legacy:funds:1")
        query = f"?account_id={account.id}"
    else:
        query = f"?account_id={selection}"

    response = client.get(f"/api/account/export{query}")

    assert response.status_code == 200
    exported = response.json()
    assert exported["format"] == "finanzr-workspace-v4"
    for section, route in {
        "real_estate": "real-estate",
        "budget": "budget",
        "funds": "funds",
        "stocks": "stocks",
        "cryptos": "cryptos",
        "orders": "orders",
        "stock_orders": "stock-orders",
        "crypto_orders": "crypto-orders",
        "fund_prices": "fund-prices",
        "stock_prices": "stock-prices",
        "crypto_prices": "crypto-prices",
    }.items():
        assert exported[section] == client.get(f"/api/{route}{query}").json()


def test_export_preserves_price_section_errors_without_losing_other_sections(
    api_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = api_context

    def unavailable(*_args: object, **_kwargs: object) -> FxConversion:
        raise CurrencyConversionError("Synthetic conversion unavailable")

    monkeypatch.setattr(market_queries, "rate_to_base", unavailable)

    response = client.get("/api/account/export")

    assert response.status_code == 200
    exported = response.json()
    for section in ("fund_prices", "stock_prices", "crypto_prices"):
        assert exported[section] == {"error": "Synthetic conversion unavailable"}
    assert len(exported["orders"]) == 1
    assert len(exported["stock_orders"]) == 1
    assert len(exported["crypto_orders"]) == 1
    assert exported["summary"] == client.get("/api/summary").json()
