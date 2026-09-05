from decimal import Decimal
from uuid import UUID

import pytest
from apps.accounts.models import Account
from apps.api.position_projection import PositionProjectionError, native_position_rows
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
)
from apps.portfolio.models import ManualAsset
from apps.users.models import User
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
        for row in response.json():
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
