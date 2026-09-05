from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from apps.api import market_views
from apps.market_data.fx import CurrencyConversionError, FxConversion
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    MarketPrice,
    StockSplit,
    WorkspaceInstrument,
)
from apps.market_data.yahoo import MarketDataError
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from django.core.cache import cache
from django.db import connection
from rest_framework.test import APIClient


@pytest.mark.django_db(transaction=True)
def test_crypto_chart_returns_ohlc_data(
    traded_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = traded_context
    monkeypatch.setattr(
        market_views,
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

    crypto_id = Instrument.objects.get(kind=Instrument.Kind.CRYPTO).pk
    response = client.get(f"/api/crypto-chart/{crypto_id}?range=1m&interval=1d")

    assert response.status_code == 200
    assert response.json()["instrument_id"] == str(crypto_id)
    assert response.json()["currency"] == "EUR"
    assert response.json()["base_currency"] == "EUR"
    assert set(response.json()) == {
        "instrument_id",
        "ticker",
        "currency",
        "base_currency",
        "range",
        "data",
    }
    assert set(response.json()["data"][0]) == {
        "date",
        "open",
        "high",
        "low",
        "close",
    }
    assert response.json()["data"][0]["close"] == 70000


@pytest.mark.django_db(transaction=True)
def test_market_charts_use_native_uuid_rows_and_per_date_fx(
    traded_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = traded_context
    instrument_ids: dict[str, str] = {
        "fund": str(Instrument.objects.get(kind=Instrument.Kind.FUND).pk),
        "stock": str(Instrument.objects.get(kind=Instrument.Kind.STOCK).pk),
        "crypto": str(Instrument.objects.get(kind=Instrument.Kind.CRYPTO).pk),
    }
    calls: list[dict[str, Any]] = []

    def fake_chart(
        ticker: str, **kwargs: str | None
    ) -> tuple[dict[str, str], list[dict[str, int | str]]]:
        calls.append({"ticker": ticker, **kwargs})
        return (
            {"currency": "USD"},
            [
                {
                    "fecha": "2026-01-01",
                    "precio": 10,
                    "open": 9,
                    "high": 11,
                    "low": 8,
                    "close": 10,
                    "provider_only": "must-not-leak",
                },
                {
                    "fecha": "2026-01-02",
                    "precio": 20,
                    "open": 19,
                    "high": 21,
                    "low": 18,
                    "close": 20,
                    "provider_only": "must-not-leak",
                },
            ],
        )

    def fake_rates(
        _currency: str,
        _base_currency: str,
        dates: list[date],
        *,
        workspace: Any,
    ) -> dict[date, FxConversion]:
        assert workspace is not None
        assert dates == [date(2026, 1, 1), date(2026, 1, 2)]
        return {
            dates[0]: FxConversion(Decimal("1.23456789"), dates[0], "test"),
            dates[1]: FxConversion(Decimal("0.987654321"), dates[1], "test"),
        }

    monkeypatch.setattr(market_views, "yahoo_chart", fake_chart)
    monkeypatch.setattr(market_views, "rates_to_base", fake_rates)

    for kind, expected_keys in {
        "fund": {"date", "close"},
        "stock": {"date", "open", "high", "low", "close"},
        "crypto": {"date", "open", "high", "low", "close"},
    }.items():
        response = client.get(
            f"/api/{kind}-chart/{instrument_ids[kind]}"
            "?range=2y&interval=invalid&start=2026-01-01&end=2026-01-02"
        )
        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {
            "instrument_id",
            "ticker",
            "currency",
            "base_currency",
            "range",
            "data",
        }
        assert payload["instrument_id"] == instrument_ids[kind]
        assert payload["currency"] == "USD"
        assert payload["base_currency"] == "EUR"
        assert payload["range"] == "2y"
        assert all(set(point) == expected_keys for point in payload["data"])

        if kind == "fund":
            assert payload["data"] == [
                {"date": "2026-01-01", "close": 12.345679},
                {"date": "2026-01-02", "close": 19.753086},
            ]
        else:
            assert payload["data"][0] == {
                "date": "2026-01-01",
                "open": 11.111111,
                "high": 13.580247,
                "low": 9.876543,
                "close": 12.345679,
            }

    assert [call["interval"] for call in calls] == ["1d", "1d", "1d"]
    assert all(
        call["range_name"] == "2y" and call["start"] == "2026-01-01" and call["end"] == "2026-01-02"
        for call in calls
    )


@pytest.mark.django_db(transaction=True)
def test_market_chart_uuid_scope_rejects_before_provider_access(
    traded_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = traded_context
    fund = Instrument.objects.get(kind=Instrument.Kind.FUND)
    foreign_workspace = Workspace.objects.create(
        name="Foreign chart workspace",
        slug="foreign-chart-workspace",
        base_currency="EUR",
    )
    foreign_stock = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="Foreign chart stock",
        quote_currency="EUR",
    )
    WorkspaceInstrument.objects.create(workspace=foreign_workspace, instrument=foreign_stock)

    provider_calls = 0

    def unexpected_ticker(_instrument: Instrument) -> str:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("Rejected chart requests must not access the provider")

    monkeypatch.setattr(market_views, "yahoo_ticker", unexpected_ticker)
    for path in (
        f"/api/stock-chart/{UUID(int=0)}",
        f"/api/stock-chart/{fund.pk}",
        f"/api/stock-chart/{foreign_stock.pk}",
        "/api/stock-chart/not-a-uuid",
        "/api/stock-chart/SYNTH-STOCK-001",
    ):
        res = client.get(path)
        assert res.status_code == 404
    assert provider_calls == 0


@pytest.mark.django_db(transaction=True)
def test_market_chart_preserves_provider_and_currency_errors(
    traded_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = traded_context
    stock = Instrument.objects.get(kind=Instrument.Kind.STOCK)
    monkeypatch.setattr(market_views, "yahoo_ticker", lambda _instrument: "SYNTH")

    def unavailable_chart(*_args: Any, **_kwargs: Any) -> Any:
        raise MarketDataError("synthetic provider error")

    monkeypatch.setattr(market_views, "yahoo_chart", unavailable_chart)
    provider_error = client.get(f"/api/stock-chart/{stock.pk}")
    assert provider_error.status_code == 502
    assert provider_error.json() == {"error": "synthetic provider error"}

    monkeypatch.setattr(
        market_views,
        "yahoo_chart",
        lambda *_args, **_kwargs: (
            {"currency": "USD"},
            [{"fecha": "2026-01-01", "precio": 10, "open": 9, "high": 11, "low": 8, "close": 10}],
        ),
    )

    def unavailable_rates(*_args: Any, **_kwargs: Any) -> Any:
        raise CurrencyConversionError("synthetic currency error")

    monkeypatch.setattr(market_views, "rates_to_base", unavailable_rates)
    currency_error = client.get(f"/api/stock-chart/{stock.pk}")
    assert currency_error.status_code == 502
    assert currency_error.json() == {"error": "synthetic currency error"}


@pytest.mark.django_db(transaction=True)
def test_stock_split_mutations_target_the_canonical_instrument_only(
    traded_context: tuple[APIClient, User],
) -> None:
    client, owner = traded_context
    canonical = "SPLIT-SHARED-001"
    first = client.post(
        "/api/stocks",
        {
            "name": "Split canonical owner",
            "identifiers": [
                {"scheme": "isin", "value": canonical, "venue": "", "is_primary": True},
                {"scheme": "yahoo", "value": "SPLIT.A", "venue": "", "is_primary": True},
            ],
        },
        format="json",
    )
    second = client.post(
        "/api/stocks",
        {
            "name": "Split alias owner",
            "identifiers": [
                {"scheme": "isin", "value": "SPLIT-B-001", "venue": "", "is_primary": True},
                {"scheme": "isin", "value": canonical, "venue": "ALT", "is_primary": False},
                {"scheme": "yahoo", "value": "SPLIT.B", "venue": "", "is_primary": True},
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
        identifiers__value="SPLIT-B-001",
    )
    workspace = Workspace.objects.get(memberships__user=owner)
    split_date = date(2026, 8, 1)
    first_split = StockSplit.objects.create(
        workspace=workspace,
        instrument=first_instrument,
        effective_date=split_date,
        ratio=Decimal("2"),
        source="first",
    )
    second_split = StockSplit.objects.create(
        workspace=workspace,
        instrument=second_instrument,
        effective_date=split_date,
        ratio=Decimal("3"),
        source="second",
    )

    deleted = client.delete(f"/api/stock-splits/{first_split.pk}")
    assert deleted.status_code == 200
    assert not StockSplit.objects.filter(pk=first_split.pk).exists()
    second_split.refresh_from_db()
    assert (second_split.instrument_id, second_split.ratio, second_split.source) == (
        second_instrument.pk,
        Decimal("3"),
        "second",
    )

    created = client.post(
        "/api/stock-splits",
        {
            "instrument_id": str(first_instrument.pk),
            "effective_date": split_date.isoformat(),
            "ratio": "4",
        },
        format="json",
    )
    assert created.status_code == 200
    assert set(created.json()) == {
        "id",
        "instrument_id",
        "effective_date",
        "ratio",
        "source",
    }
    first_split = StockSplit.objects.get(instrument=first_instrument, effective_date=split_date)
    assert created.json()["id"] == str(first_split.pk)
    second_split.refresh_from_db()
    assert (first_split.ratio, first_split.source) == (Decimal("4"), "manual")
    assert (second_split.ratio, second_split.source) == (Decimal("3"), "second")


@pytest.mark.django_db(transaction=True)
def test_native_stock_split_contract_rejects_invalid_payloads_without_mutation(
    traded_context: tuple[APIClient, User],
) -> None:
    client, owner = traded_context
    stock = Instrument.objects.get(
        identifiers__scheme=InstrumentIdentifier.Scheme.ISIN,
        identifiers__value="SYNTH-STOCK-001",
    )
    fund = Instrument.objects.get(
        identifiers__scheme=InstrumentIdentifier.Scheme.ISIN,
        identifiers__value="SYNTH-FUND-001",
    )
    split = StockSplit.objects.get(instrument=stock)

    listed = client.get("/api/stock-splits")
    assert listed.status_code == 200
    listed_row = next(row for row in listed.json() if row["id"] == str(split.pk))
    assert set(listed_row) == {
        "id",
        "instrument_id",
        "effective_date",
        "ratio",
        "source",
    }
    assert listed_row["instrument_id"] == str(stock.pk)
    assert listed_row["effective_date"] == split.effective_date.isoformat()
    assert listed_row["ratio"] == 2.0

    updated = client.post(
        "/api/stock-splits",
        {
            "instrument_id": str(stock.pk),
            "effective_date": split.effective_date.isoformat(),
            "ratio": "0.5",
        },
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == str(split.pk)
    split.refresh_from_db()
    assert (split.ratio, split.source) == (Decimal("0.5"), "manual")

    split_count = StockSplit.objects.filter(workspace=split.workspace).count()
    minimum = client.post(
        "/api/stock-splits",
        {
            "instrument_id": str(stock.pk),
            "effective_date": split.effective_date.isoformat(),
            "ratio": "0.000000000001",
            "source": "boundary",
        },
        format="json",
    )
    assert minimum.status_code == 200
    assert minimum.json()["id"] == str(split.pk)
    maximum = None
    if connection.vendor != "sqlite":
        maximum = client.post(
            "/api/stock-splits",
            {
                "instrument_id": str(stock.pk),
                "effective_date": split.effective_date.isoformat(),
                "ratio": "999999999999.999999999999",
                "source": "boundary",
            },
            format="json",
        )
        assert maximum.status_code == 200
        assert maximum.json()["id"] == str(split.pk)
    split.refresh_from_db()
    if maximum is not None:
        assert split.ratio == Decimal("999999999999.999999999999")
        assert split.source == "boundary"
    else:
        assert split.ratio == Decimal("0.000000000001")
        assert split.source == "boundary"
    assert split.confirmed_by_id == owner.pk
    assert StockSplit.objects.filter(workspace=split.workspace).count() == split_count

    cache_key = "native-stock-split-invalid-payload"
    cache.set(cache_key, "sentinel", timeout=3600)
    valid_body = {
        "instrument_id": str(stock.pk),
        "effective_date": split.effective_date.isoformat(),
        "ratio": "2",
    }
    invalid_payloads = [
        {"isin": "SYNTH-STOCK-001", "fecha": "2026-01-01", "ratio": 2},
        {**valid_body, "id": str(split.pk)},
        {**valid_body, "ratio": 0},
        {**valid_body, "ratio": -1},
        {**valid_body, "ratio": "NaN"},
        {**valid_body, "ratio": "Infinity"},
        {**valid_body, "ratio": "0.0000000000001"},
        {**valid_body, "ratio": "1000000000000"},
        {**valid_body, "ratio": True},
        {**valid_body, "source": ""},
        {**valid_body, "source": None},
        {**valid_body, "source": "x" * 121},
        {**valid_body, "fuente": "manual"},
        {**valid_body, "effective_date": "not-a-date"},
        {**valid_body, "instrument_id": "not-a-uuid"},
        {**valid_body, "instrument_id": str(fund.pk)},
        {**valid_body, "instrument_id": str(UUID(int=0))},
    ]
    for body in invalid_payloads:
        response = client.post("/api/stock-splits", body, format="json")
        assert response.status_code == 400, (body, response.content)
        assert cache.get(cache_key) == "sentinel"

    split.refresh_from_db()
    if maximum is not None:
        assert (split.ratio, split.source) == (
            Decimal("999999999999.999999999999"),
            "boundary",
        )
    else:
        assert (split.ratio, split.source) == (Decimal("0.000000000001"), "boundary")


def _active_workspace(client: APIClient) -> Workspace:
    return Workspace.objects.get(pk=client.session["active_workspace_id"])


def _foreign_stock_split(label: str) -> StockSplit:
    foreign_workspace = Workspace.objects.create(
        name=f"Foreign {label} split workspace",
        slug=f"foreign-{label}-split-workspace",
        base_currency="EUR",
    )
    foreign_stock = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name=f"Foreign {label} split stock",
        quote_currency="EUR",
    )
    WorkspaceInstrument.objects.create(workspace=foreign_workspace, instrument=foreign_stock)
    return StockSplit.objects.create(
        workspace=foreign_workspace,
        instrument=foreign_stock,
        effective_date=date(2026, 2, 1),
        ratio=Decimal("3"),
        source="foreign",
    )


@pytest.mark.django_db(transaction=True)
def test_stock_split_instrument_isolation_rejects_foreign_post_and_hides_foreign_rows(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    current_workspace = _active_workspace(client)
    current_stock = Instrument.objects.get(
        identifiers__scheme=InstrumentIdentifier.Scheme.ISIN,
        identifiers__value="SYNTH-STOCK-001",
    )
    current_split = StockSplit.objects.get(workspace=current_workspace, instrument=current_stock)
    foreign_split = _foreign_stock_split("post")
    foreign_stock = foreign_split.instrument

    listed_ids = {row["id"] for row in client.get("/api/stock-splits").json()}
    assert str(current_split.pk) in listed_ids
    assert str(foreign_split.pk) not in listed_ids

    cache_key = "foreign-stock-split-isolation"
    cache.set(cache_key, "sentinel", timeout=3600)
    response = client.post(
        "/api/stock-splits",
        {
            "instrument_id": str(foreign_stock.pk),
            "effective_date": "2026-02-01",
            "ratio": 2,
        },
        format="json",
    )
    assert response.status_code == 400
    assert cache.get(cache_key) == "sentinel"
    assert StockSplit.objects.filter(pk=current_split.pk).exists()
    assert StockSplit.objects.filter(pk=foreign_split.pk).exists()


@pytest.mark.parametrize("target", ("foreign", "missing", "wrong-kind", "malformed", "legacy"))
@pytest.mark.django_db(transaction=True)
def test_stock_split_delete_is_scoped_and_rejects_non_native_routes(
    traded_context: tuple[APIClient, User], target: str
) -> None:
    client, _ = traded_context
    current_workspace = _active_workspace(client)
    current_split = StockSplit.objects.get(workspace=current_workspace)
    wrong_kind_split = None
    if target == "wrong-kind":
        fund = Instrument.objects.get(
            identifiers__scheme=InstrumentIdentifier.Scheme.ISIN,
            identifiers__value="SYNTH-FUND-001",
        )
        wrong_kind_split = StockSplit.objects.create(
            workspace=current_workspace,
            instrument=fund,
            effective_date=date(2026, 3, 1),
            ratio=Decimal("2"),
            source="wrong-kind",
        )
    foreign_split = _foreign_stock_split("delete") if target == "foreign" else None
    targets = {
        "foreign": f"/api/stock-splits/{foreign_split.pk}" if foreign_split else "",
        "missing": f"/api/stock-splits/{UUID(int=0)}",
        "wrong-kind": f"/api/stock-splits/{wrong_kind_split.pk}" if wrong_kind_split else "",
        "malformed": "/api/stock-splits/not-a-uuid",
        "legacy": "/api/stock-splits/SYNTH-STOCK-001/2026-01-01",
    }
    cache_key = f"stock-split-delete-rejection-{target}"
    cache.set(cache_key, "sentinel", timeout=3600)
    response = client.delete(targets[target])
    assert response.status_code == 404
    assert cache.get(cache_key) == "sentinel"
    assert StockSplit.objects.filter(pk=current_split.pk).exists()
    if wrong_kind_split:
        assert StockSplit.objects.filter(pk=wrong_kind_split.pk).exists()
    if foreign_split:
        assert StockSplit.objects.filter(pk=foreign_split.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_viewer_cannot_mutate_stock_splits(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    current_workspace = _active_workspace(client)
    split = StockSplit.objects.get(workspace=current_workspace)
    stock = split.instrument
    viewer = User.objects.create_user(email="stock-split-viewer@example.com")
    WorkspaceMembership.objects.create(
        workspace=current_workspace,
        user=viewer,
        role=WorkspaceMembership.Role.VIEWER,
    )
    viewer_client = APIClient()
    viewer_client.force_authenticate(user=viewer)
    session = viewer_client.session
    session["active_workspace_id"] = str(current_workspace.pk)
    session.save()

    cache_key = "stock-split-viewer-rejection"
    cache.set(cache_key, "sentinel", timeout=3600)
    body = {
        "instrument_id": str(stock.pk),
        "effective_date": split.effective_date.isoformat(),
        "ratio": 2,
    }
    post = viewer_client.post("/api/stock-splits", body, format="json")
    delete = viewer_client.delete(f"/api/stock-splits/{split.pk}")
    assert post.status_code == delete.status_code == 403
    assert cache.get(cache_key) == "sentinel"
    assert StockSplit.objects.filter(pk=split.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_price_refresh_endpoints_share_the_internal_handler(
    traded_context: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = traded_context
    monkeypatch.setattr(market_views, "yahoo_ticker", lambda _instrument: "TEST")
    monkeypatch.setattr(market_views, "quote_price", lambda _ticker: (100.0, "USD"))
    monkeypatch.setattr(
        market_views,
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
        assert all(item["base_close"] == 90.0 for item in response.json()["results"])
        assert all(item["close"] == 100.0 for item in response.json()["results"])


@pytest.mark.django_db(transaction=True)
def test_stock_prices_and_analysis_use_only_the_latest_spot_quote(
    traded_context: tuple[APIClient, User],
) -> None:
    client, _ = traded_context
    transaction = (
        Transaction.objects.filter(instrument__kind="stock").select_related("instrument").first()
    )
    assert transaction is not None
    instrument = transaction.instrument
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
    matching_prices = [row for row in prices.json() if row["instrument_id"] == str(instrument.id)]
    assert matching_prices == [
        {
            "id": str(MarketPrice.objects.get(instrument=instrument, source="test-latest").id),
            "instrument_id": str(instrument.id),
            "quoted_at": "2030-01-01T12:00:00+00:00",
            "close": 123.45,
            "currency": "EUR",
            "base_close": 123.45,
            "base_currency": "EUR",
            "fx_rate_to_base": 1.0,
            "fx_rate_date": "2030-01-01",
            "fx_source": "identity",
            "source": "test-latest",
        }
    ]
    assert analysis.status_code == 200
    position = next(row for row in analysis.json() if row["instrument_id"] == str(instrument.id))
    assert position["current_price"] == 123.45
