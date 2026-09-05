from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from apps.accounts.models import Account
from apps.api import instrument_views, market_queries, market_views
from apps.api.market_data_projection import instrument_calculation_row
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    WorkspaceInstrument,
    WorkspaceMarketPriceOverride,
)
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    ("collection", "identity_scheme", "identifier", "ticker"),
    [
        ("/api/stocks", "isin", "US0378331005", "AAPL"),
        ("/api/cryptos", "crypto_symbol", "SOL", "SOL-EUR"),
    ],
)
def test_stock_and_crypto_assets_can_be_created_and_edit_their_ticker(
    api_context: tuple[APIClient, User],
    collection: str,
    identity_scheme: str,
    identifier: str,
    ticker: str,
) -> None:
    client, _ = api_context
    transaction_count = Transaction.objects.count()

    created = client.post(
        collection,
        {
            "name": "Activo manual",
            "quote_currency": "EUR",
            "identifiers": [
                {"scheme": identity_scheme, "value": identifier, "is_primary": True},
                {"scheme": "yahoo", "value": ticker, "is_primary": True},
            ],
        },
        format="json",
    )

    assert created.status_code == 201
    assert created.json()["kind"] == ("crypto" if identity_scheme == "crypto_symbol" else "stock")
    assert created.json()["name"] == "Activo manual"
    assert created.json()["id"]
    assert {(row["scheme"], row["value"]) for row in created.json()["identifiers"]} == {
        (identity_scheme, identifier),
        ("yahoo", ticker),
    }
    assert Transaction.objects.count() == transaction_count
    assert WorkspaceInstrument.objects.filter(
        instrument__identifiers__scheme=identity_scheme,
        instrument__identifiers__value=identifier,
    ).exists()
    assert any(
        any(
            identity["scheme"] == identity_scheme and identity["value"] == identifier
            for identity in row["identifiers"]
        )
        for row in client.get(collection).json()
    )

    updated = client.put(
        f"{collection}/{created.json()['id']}",
        {
            "name": "Activo editado",
            "identifiers": [
                {"scheme": identity_scheme, "value": identifier, "is_primary": True},
                {"scheme": "yahoo", "value": f"{ticker}.EDIT", "is_primary": True},
            ],
        },
        format="json",
    )

    assert updated.status_code == 200
    assert updated.json()["name"] == "Activo editado"
    assert {(row["scheme"], row["value"]) for row in updated.json()["identifiers"]} == {
        (identity_scheme, identifier),
        ("yahoo", f"{ticker}.EDIT"),
    }


@pytest.mark.django_db(transaction=True)
def test_native_instrument_contract_is_strict_uuid_scoped_and_preserves_identities(
    api_context: tuple[APIClient, User],
) -> None:
    client, owner = api_context
    workspace = Workspace.objects.get(pk=client.session["active_workspace_id"])
    body = {
        "name": "Native contract stock",
        "quote_currency": "eur",
        "identifiers": [
            {"scheme": "isin", "value": "NATIVE-STOCK-001", "is_primary": True},
            {"scheme": "yahoo", "value": "NATIVE.MC", "is_primary": True},
        ],
        "asset_class": "Equity",
        "subtype": None,
        "is_active": True,
    }

    created = client.post("/api/stocks", body, format="json")
    assert created.status_code == 201
    row = created.json()
    assert set(row) == {
        "id",
        "kind",
        "name",
        "quote_currency",
        "identifiers",
        "asset_class",
        "subtype",
        "is_active",
    }
    UUID(row["id"])
    assert row["kind"] == "stock"
    assert row["quote_currency"] == "EUR"
    assert "metadata" not in row and "legacy_id" not in row

    assert (
        client.post(
            "/api/stocks",
            {"nombre": "Legacy", "isin": "NATIVE-STOCK-002", "ticker": "OLD"},
            format="json",
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/stocks",
            {
                "name": "Wrong scheme",
                "identifiers": [{"scheme": "crypto_symbol", "value": "BTC"}],
            },
            format="json",
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/cryptos",
            {
                "name": "Missing crypto identity",
                "identifiers": [{"scheme": "yahoo", "value": "BTC-EUR"}],
            },
            format="json",
        ).status_code
        == 400
    )
    listed_funds = client.get("/api/funds")
    assert listed_funds.status_code == 200
    assert listed_funds.json()
    assert listed_funds.json()[0]["kind"] == "fund"
    assert set(listed_funds.json()[0]) == {
        "id",
        "kind",
        "name",
        "quote_currency",
        "identifiers",
        "asset_class",
        "subtype",
        "is_active",
    }

    updated = client.put(
        f"/api/stocks/{row['id']}",
        {
            "name": "Native contract stock edited",
            "identifiers": [
                {"scheme": "isin", "value": " native-stock-001 ", "is_primary": True},
                {"scheme": "yahoo", "value": "NATIVE-EDIT.MC", "is_primary": True},
            ],
        },
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Native contract stock edited"
    assert {item["value"] for item in updated.json()["identifiers"]} == {
        "NATIVE-STOCK-001",
        "NATIVE-EDIT.MC",
    }
    assert InstrumentIdentifier.objects.filter(
        instrument_id=row["id"], scheme=InstrumentIdentifier.Scheme.ISIN, value="NATIVE-STOCK-001"
    ).exists()
    assert (
        instrument_calculation_row(
            Instrument.objects.prefetch_related("identifiers").get(pk=row["id"])
        )["isin"]
        == "NATIVE-STOCK-001"
    )
    net_worth_res = client.get("/api/net-worth-history")
    assert net_worth_res.status_code == 200

    wrong_kind_res = client.put(f"/api/cryptos/{row['id']}", {"name": "Wrong kind"}, format="json")
    assert wrong_kind_res.status_code == 404

    isolated_workspace = Workspace.objects.create(
        name="Isolated native workspace",
        slug="isolated-native-workspace",
        base_currency="EUR",
        timezone="Europe/Madrid",
    )
    WorkspaceMembership.objects.create(
        workspace=isolated_workspace,
        user=owner,
        role=WorkspaceMembership.Role.OWNER,
    )
    session = client.session
    session["active_workspace_id"] = str(isolated_workspace.pk)
    session.save()
    assert client.get("/api/stocks").json() == []
    assert (
        client.put(
            f"/api/stocks/{row['id']}",
            {"name": "Should not cross workspaces"},
            format="json",
        ).status_code
        == 404
    )

    viewer = User.objects.create_user(email="viewer-native@example.com", password="synthetic")
    WorkspaceMembership.objects.create(
        workspace=workspace,
        user=viewer,
        role=WorkspaceMembership.Role.VIEWER,
    )
    viewer_client = APIClient()
    viewer_client.force_authenticate(user=viewer)
    viewer_session = viewer_client.session
    viewer_session["active_workspace_id"] = str(workspace.pk)
    viewer_session.save()
    assert (
        viewer_client.put(
            f"/api/stocks/{row['id']}", {"name": "Viewer edit"}, format="json"
        ).status_code
        == 403
    )


@pytest.mark.django_db(transaction=True)
def test_instrument_name_only_update_keeps_currency_seen_after_lock(
    api_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = api_context
    instrument = Instrument.objects.get(kind=Instrument.Kind.STOCK)

    def change_currency_during_lock(_keys: object) -> None:
        Instrument.objects.filter(pk=instrument.pk).update(quote_currency="USD")

    monkeypatch.setattr(instrument_views, "lock_logical_keys", change_currency_during_lock)
    response = client.put(
        f"/api/stocks/{instrument.pk}",
        {"name": "Currency-safe edit"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["quote_currency"] == "USD"
    instrument.refresh_from_db()
    assert instrument.name == "Currency-safe edit"
    assert instrument.quote_currency == "USD"


@pytest.mark.django_db(transaction=True)
def test_identifier_selection_matches_public_projection_and_market_consumers(
    api_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, owner = api_context
    workspace = Workspace.objects.get(memberships__user=owner)
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="Identifier selection stock",
        quote_currency="EUR",
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value="SELECT-001",
        venue="",
        is_primary=False,
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.YAHOO,
        value="SELECT.STALE",
        venue="NASDAQ",
        is_primary=False,
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.YAHOO,
        value="SELECT.LIVE",
        venue="BME",
        is_primary=True,
    )
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=instrument)

    public = next(
        row for row in client.get("/api/stocks").json() if row["id"] == str(instrument.pk)
    )
    assert {row["value"] for row in public["identifiers"]} == {
        "SELECT-001",
        "SELECT.STALE",
        "SELECT.LIVE",
    }
    assert market_queries.yahoo_ticker(instrument) == "SELECT.LIVE"
    assert instrument_calculation_row(instrument)["ticker"] == "SELECT.LIVE"

    switched = client.put(
        f"/api/stocks/{instrument.pk}",
        {
            "identifiers": [
                {"scheme": "isin", "value": "SELECT-001", "is_primary": False},
                {
                    "scheme": "yahoo",
                    "value": "SELECT.STALE",
                    "venue": "NASDAQ",
                    "is_primary": True,
                },
                {
                    "scheme": "yahoo",
                    "value": "SELECT.LIVE",
                    "venue": "BME",
                    "is_primary": False,
                },
            ]
        },
        format="json",
    )
    assert switched.status_code == 200
    assert (
        next(
            row
            for row in switched.json()["identifiers"]
            if row["scheme"] == "yahoo" and row["is_primary"]
        )["value"]
        == "SELECT.STALE"
    )

    instrument.refresh_from_db()
    assert market_queries.yahoo_ticker(instrument) == "SELECT.STALE"
    assert instrument_calculation_row(instrument)["ticker"] == "SELECT.STALE"

    chart_tickers: list[str] = []

    def fake_chart(
        ticker: str, **_kwargs: Any
    ) -> tuple[dict[str, str], list[dict[str, int | str]]]:
        chart_tickers.append(ticker)
        return (
            {"currency": "EUR"},
            [
                {
                    "fecha": "2026-01-01",
                    "precio": 10,
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10,
                }
            ],
        )

    monkeypatch.setattr(
        market_views,
        "yahoo_chart",
        fake_chart,
    )
    chart = client.get(f"/api/stock-chart/{instrument.pk}")
    assert chart.status_code == 200
    assert chart.json()["ticker"] == "SELECT.STALE"
    assert chart_tickers == ["SELECT.STALE"]

    fetch_tickers: list[str] = []

    def fake_quote(ticker: str) -> tuple[float, str]:
        fetch_tickers.append(ticker)
        return 10.0, "EUR"

    monkeypatch.setattr(
        market_views,
        "quote_price",
        fake_quote,
    )
    fetched = client.post("/api/stock-prices/fetch", format="json")
    assert fetched.status_code == 200
    selected_result = next(
        row for row in fetched.json()["results"] if row["instrument_id"] == str(instrument.id)
    )
    assert selected_result["ticker"] == "SELECT.STALE"
    assert "SELECT.STALE" in fetch_tickers


@pytest.mark.django_db(transaction=True)
def test_canonical_identity_resolvers_ignore_nondefault_aliases(
    api_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = api_context
    canonical = "SHARED-VALUE-001"
    first = client.post(
        "/api/stocks",
        {
            "name": "Canonical owner",
            "quote_currency": "EUR",
            "identifiers": [
                {"scheme": "isin", "value": canonical, "venue": "", "is_primary": True},
                {"scheme": "yahoo", "value": "OWNER.MC", "venue": "", "is_primary": True},
            ],
        },
        format="json",
    )
    second = client.post(
        "/api/stocks",
        {
            "name": "Alias owner",
            "quote_currency": "EUR",
            "identifiers": [
                {"scheme": "isin", "value": "OTHER-001", "venue": "", "is_primary": True},
                {"scheme": "isin", "value": canonical, "venue": "ALT", "is_primary": False},
                {"scheme": "yahoo", "value": "ALIAS.MC", "venue": "", "is_primary": True},
            ],
        },
        format="json",
    )
    assert first.status_code == 201
    assert second.status_code == 201
    first_instrument = Instrument.objects.get(
        identifiers__scheme=InstrumentIdentifier.Scheme.ISIN,
        identifiers__value=canonical,
        identifiers__venue="",
    )
    second_instrument = Instrument.objects.get(
        identifiers__scheme=InstrumentIdentifier.Scheme.ISIN,
        identifiers__value="OTHER-001",
    )
    assert first_instrument.pk != second_instrument.pk

    monkeypatch.setattr(
        market_views,
        "yahoo_chart",
        lambda *_args, **_kwargs: (
            {"currency": "EUR"},
            [
                {
                    "fecha": "2026-01-01",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10,
                }
            ],
        ),
    )
    chart = client.get(f"/api/stock-chart/{first_instrument.pk}")
    assert chart.status_code == 200
    assert chart.json()["ticker"] == "OWNER.MC"
    legacy_chart = client.get(f"/api/stock-chart/{canonical}")
    assert legacy_chart.status_code == 404

    price = client.put(f"/api/stock-prices/{first_instrument.pk}", {"close": 123}, format="json")
    assert price.status_code == 200
    override = WorkspaceMarketPriceOverride.objects.get(instrument=first_instrument)
    assert override.close == Decimal("123")
    assert not WorkspaceMarketPriceOverride.objects.filter(instrument=second_instrument).exists()

    account = Account.objects.get(kind=Account.Kind.STOCKS)
    order = client.post(
        "/api/stock-orders",
        {
            "account_id": str(account.pk),
            "isin": canonical,
            "trade_date": "2026-07-25",
            "operation_type": "buy",
            "quantity": 1,
            "unit_price": 25,
            "net_amount": 25,
            "fee": 0,
        },
        format="json",
    )
    assert order.status_code == 201
    assert Transaction.objects.get(pk=order.json()["id"]).instrument_id == (first_instrument.pk)


@pytest.mark.django_db(transaction=True)
def test_native_identifier_sets_validate_before_writes_and_support_fund_clear(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    body = {
        "name": "Primary venue stock",
        "quote_currency": "EUR",
        "identifiers": [
            {"scheme": "isin", "value": "PRIMARY-001", "is_primary": True},
            {
                "scheme": "yahoo",
                "value": "PRIMARY.DE",
                "venue": "XETRA",
                "is_primary": False,
            },
            {
                "scheme": "yahoo",
                "value": "PRIMARY.MC",
                "venue": "BME",
                "is_primary": True,
            },
        ],
        "asset_class": "Equity",
        "subtype": "Large cap",
    }
    created = client.post("/api/stocks", body, format="json")
    assert created.status_code == 201
    item_id = created.json()["id"]

    def state() -> tuple[object, object, object, object, list[tuple[str, str, str, bool]]]:
        item = Instrument.objects.get(pk=item_id)
        return (
            item.name,
            item.quote_currency,
            item.is_active,
            dict(item.metadata),
            list(
                item.identifiers.order_by("scheme", "venue", "value").values_list(
                    "scheme", "value", "venue", "is_primary"
                )
            ),
        )

    before = state()
    malformed_requests = [
        {
            "name": "Duplicate slot",
            "identifiers": [
                {"scheme": "isin", "value": "DUP-001", "is_primary": True},
                {"scheme": "yahoo", "value": "DUP.DE", "venue": "BME"},
                {"scheme": "yahoo", "value": "DUP.MC", "venue": "BME"},
            ],
        },
        {
            "name": "Multiple primary",
            "identifiers": [
                {"scheme": "isin", "value": "MULTI-001", "is_primary": True},
                {"scheme": "yahoo", "value": "MULTI.DE", "is_primary": True},
                {"scheme": "yahoo", "value": "MULTI.MC", "is_primary": True},
            ],
        },
    ]
    for malformed in malformed_requests:
        malformed_res = client.post("/api/stocks", malformed, format="json")
        assert malformed_res.status_code == 400
    noncanon_res = client.post(
        "/api/stocks",
        {
            "name": "Noncanonical",
            "identifiers": [{"scheme": "isin", "value": "NONCANON", "venue": "BME"}],
        },
        format="json",
    )
    assert noncanon_res.status_code == 400

    rejected_identity = client.put(
        f"/api/stocks/{item_id}",
        {
            "name": "Must not persist",
            "quote_currency": "USD",
            "asset_class": "Changed",
            "subtype": "Changed",
            "identifiers": [{"scheme": "isin", "value": "DIFFERENT", "is_primary": True}],
        },
        format="json",
    )
    assert rejected_identity.status_code == 400
    assert state() == before

    primary_conflict = client.put(
        f"/api/stocks/{item_id}",
        {
            "name": "Must not persist primary conflict",
            "identifiers": [
                {
                    "scheme": "yahoo",
                    "value": "PRIMARY.NEW",
                    "venue": "NASDAQ",
                    "is_primary": True,
                }
            ],
        },
        format="json",
    )
    assert primary_conflict.status_code == 400
    assert state() == before

    conflict = client.post(
        "/api/stocks",
        {
            "name": "Conflicting stock",
            "identifiers": [
                {"scheme": "isin", "value": "CONFLICT-001", "is_primary": True},
                {"scheme": "yahoo", "value": "CONFLICT.MC", "is_primary": True},
            ],
        },
        format="json",
    )
    assert conflict.status_code == 201
    conflicting_update = client.put(
        f"/api/stocks/{item_id}",
        {
            "name": "Must not persist conflict",
            "identifiers": [
                {"scheme": "isin", "value": "PRIMARY-001", "is_primary": True},
                {
                    "scheme": "yahoo",
                    "value": "PRIMARY.DE",
                    "venue": "XETRA",
                    "is_primary": False,
                },
                {
                    "scheme": "yahoo",
                    "value": "PRIMARY.MC",
                    "venue": "BME",
                    "is_primary": False,
                },
                {
                    "scheme": "yahoo",
                    "value": "CONFLICT.MC",
                    "venue": "",
                    "is_primary": True,
                },
            ],
        },
        format="json",
    )
    assert conflicting_update.status_code == 400
    assert state() == before

    transitioned = client.put(
        f"/api/stocks/{item_id}",
        {
            "identifiers": [
                {"scheme": "isin", "value": "PRIMARY-001", "is_primary": True},
                {
                    "scheme": "yahoo",
                    "value": "PRIMARY.DE",
                    "venue": "XETRA",
                    "is_primary": False,
                },
                {
                    "scheme": "yahoo",
                    "value": "PRIMARY.MC",
                    "venue": "BME",
                    "is_primary": False,
                },
                {
                    "scheme": "yahoo",
                    "value": "PRIMARY.NEW",
                    "venue": "NASDAQ",
                    "is_primary": True,
                },
            ],
        },
        format="json",
    )
    assert transitioned.status_code == 200
    assert [
        (row["scheme"], row["value"], row["venue"], row["is_primary"])
        for row in transitioned.json()["identifiers"]
    ] == [
        ("isin", "PRIMARY-001", "", True),
        ("yahoo", "PRIMARY.DE", "XETRA", False),
        ("yahoo", "PRIMARY.MC", "BME", False),
        ("yahoo", "PRIMARY.NEW", "NASDAQ", True),
    ]

    fund = client.get("/api/funds").json()[0]
    fund_id = fund["id"]
    fund_before_metadata = dict(Instrument.objects.get(pk=fund_id).metadata)
    cleared = client.put(
        f"/api/funds/{fund_id}",
        {"identifiers": [{"scheme": "yahoo", "value": "", "venue": "", "is_primary": True}]},
        format="json",
    )
    assert cleared.status_code == 200
    assert not any(row["scheme"] == "yahoo" for row in cleared.json()["identifiers"])
    assert Instrument.objects.get(pk=fund_id).metadata == fund_before_metadata
    assert InstrumentIdentifier.objects.filter(
        instrument_id=fund_id, scheme=InstrumentIdentifier.Scheme.ISIN
    ).exists()
    assert (
        client.put(
            f"/api/stocks/{item_id}",
            {
                "identifiers": [
                    {"scheme": "isin", "value": "PRIMARY-001", "is_primary": True},
                    {"scheme": "yahoo", "value": "", "is_primary": True},
                ]
            },
            format="json",
        ).status_code
        == 400
    )
