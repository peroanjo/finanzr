"""Focused coverage for the shared investment performance calculation."""

from datetime import date
from decimal import Decimal

import pytest
from apps.accounts.models import Account
from apps.api import views
from apps.market_data.fx import FxConversion
from apps.market_data.models import Instrument, InstrumentIdentifier, WorkspaceInstrument
from apps.workspaces.models import Workspace
from django.core.cache import cache
from rest_framework.test import APIClient

from finanzr.domain.investment_performance import (
    _record_sort_key,
    calculate_investment_performance,
)


def _workspace_client(slug: str) -> tuple[Workspace, APIClient]:
    workspace = Workspace.objects.create(name=slug, slug=slug, base_currency="EUR")
    from apps.users.models import User
    from apps.workspaces.models import WorkspaceMembership

    user = User.objects.create_user(email=f"{slug}@example.com", password="password123")
    WorkspaceMembership.objects.create(workspace=workspace, user=user, role="owner")
    client = APIClient()
    client.force_authenticate(user)
    session = client.session
    session["active_workspace_id"] = str(workspace.pk)
    session.save()
    return workspace, client


def _record(
    account: int,
    asset: str,
    day: str,
    operation: str,
    quantity: float,
    amount: float,
    *,
    kind: str = "fund",
    saveback: bool = False,
    provider: str = "",
) -> dict[str, object]:
    return {
        "cuenta_id": account,
        "symbol" if kind == "crypto" else "isin": asset,
        "fecha_operacion": day,
        "tipo_operacion": operation,
        "titulos": quantity,
        "importe_neto": amount,
        "es_saveback": saveback,
        "plataforma": provider,
    }


def test_same_day_records_use_uuid_id_as_deterministic_tie_breaker() -> None:
    first_id = "00000000-0000-0000-0000-000000000001"
    second_id = "00000000-0000-0000-0000-000000000002"
    rows = [
        {"id": second_id, "fecha_operacion": "2026-01-01"},
        {"id": first_id, "fecha_operacion": "2026-01-01"},
    ]

    ordered = sorted(rows, key=_record_sort_key)

    assert [row["id"] for row in ordered] == [first_id, second_id]


def test_funds_transfers_are_value_without_external_contribution() -> None:
    rows = [
        _record(1, "A", "2026-01-01", "SUSCRIPCION", 10, 100),
        _record(1, "A", "2026-01-02", "REEMB.POR TRASPASO I", 10, 120),
        _record(1, "B", "2026-01-03", "SUSCR.POR TRASPASO I", 12, 120),
    ]
    history = {
        "A": {"2026-01-01": 10, "2026-01-02": 12, "2026-01-03": 12},
        "B": {"2026-01-01": 10, "2026-01-02": 10, "2026-01-03": 10},
    }

    result = calculate_investment_performance(histories=history, records=rows, account_id=1)

    assert result[1] == {
        "fecha": "2026-01-02",
        "valor": 0.0,
        "invertido": 0.0,
        "pnl": 20.0,
        "pnl_pct": 20.0,
    }


def test_account_filter_does_not_leak_another_account() -> None:
    rows = [
        _record(1, "A", "2026-01-01", "SUSCRIPCION", 1, 100),
        _record(2, "A", "2026-01-01", "SUSCRIPCION", 1, 900),
    ]

    result = calculate_investment_performance(
        records=rows,
        histories={"A": {"2026-01-01": 110}},
        account_id=1,
    )

    assert result[0]["invertido"] == 100.0
    assert result[0]["valor"] == 110.0


def test_stock_split_is_applied_only_after_its_effective_date() -> None:
    rows = [_record(1, "A", "2026-01-01", "Compra", 10, 100, kind="stock")]
    result = calculate_investment_performance(
        records=rows,
        histories={"A": {"2026-01-01": 10, "2026-01-02": 5}},
        kind="stock",
        splits=[{"isin": "A", "fecha": "2026-01-02", "ratio": 2}],
    )

    assert [point["valor"] for point in result] == [100.0, 100.0]


def test_stock_saveback_has_zero_cost_only_when_requested() -> None:
    rows = [
        _record(
            1,
            "A",
            "2026-01-01",
            "Compra",
            1,
            10,
            kind="stock",
            saveback=True,
            provider="Trade Republic",
        )
    ]
    history = {"A": {"2026-01-01": 12}}

    counted = calculate_investment_performance(records=rows, histories=history, kind="stock")
    ignored = calculate_investment_performance(
        records=rows,
        histories=history,
        kind="stock",
        ignore_savebacks=True,
    )

    assert counted[0]["invertido"] == 10.0
    assert ignored[0]["invertido"] == 0.0
    assert ignored[0]["valor"] == 12.0


def test_stock_saveback_from_another_provider_keeps_its_cost() -> None:
    rows = [
        _record(
            1,
            "A",
            "2026-01-01",
            "Compra",
            1,
            10,
            kind="stock",
            saveback=True,
            provider="Broker Demo",
        )
    ]

    result = calculate_investment_performance(
        records=rows,
        histories={"A": {"2026-01-01": 12}},
        kind="stock",
        ignore_savebacks=True,
    )

    assert result[0]["invertido"] == 10.0


def test_crypto_uses_stored_net_amount_once_including_fee() -> None:
    rows = [_record(1, "BTC", "2026-01-01", "Compra", 1, 101, kind="crypto")]
    rows[0]["comision"] = 1

    result = calculate_investment_performance(
        records=rows,
        histories={"BTC": {"2026-01-01": 110}},
        kind="crypto",
    )

    assert result[0]["invertido"] == 101.0
    assert result[0]["pnl"] == 9.0


@pytest.mark.parametrize("kind, asset", [("stock", "A"), ("crypto", "BTC")])
def test_profitable_partial_and_full_sales_keep_realized_pnl(kind: str, asset: str) -> None:
    operation = "Compra"
    sell = "Venta"
    rows = [
        _record(1, asset, "2026-01-01", operation, 2, 100, kind=kind),
        _record(1, asset, "2026-01-02", sell, 1, 60, kind=kind),
        _record(1, asset, "2026-01-03", sell, 1, 70, kind=kind),
    ]

    result = calculate_investment_performance(
        records=rows,
        histories={asset: {"2026-01-01": 50, "2026-01-02": 60}},
        kind=kind,
    )

    assert result[1]["pnl"] == 20.0
    assert result[2]["valor"] == 0.0
    assert result[2]["invertido"] == 0.0
    assert result[2]["pnl"] == 30.0
    assert result[2]["pnl_pct"] == 30.0


@pytest.mark.parametrize("kind, asset", [("stock", "A"), ("crypto", "BTC")])
def test_loss_on_full_sale_uses_gross_contribution_percentage(kind: str, asset: str) -> None:
    rows = [
        _record(1, asset, "2026-01-01", "Compra", 1, 100, kind=kind),
        _record(1, asset, "2026-01-03", "Venta", 1, 80, kind=kind),
    ]
    if kind == "crypto":
        rows[1]["comision"] = 2

    result = calculate_investment_performance(
        records=rows,
        histories={asset: {"2026-01-01": 100, "2026-01-02": 90}},
        kind=kind,
    )

    assert result[-1]["fecha"] == "2026-01-03"
    assert result[-1]["valor"] == 0.0
    assert result[-1]["pnl"] == -20.0
    assert result[-1]["pnl_pct"] == -20.0


def test_two_account_fund_transfer_has_no_permanent_account_cash() -> None:
    rows = [
        _record(1, "A", "2026-01-01", "SUSCRIPCION", 10, 100),
        _record(1, "A", "2026-01-02", "REEMB.POR TRASPASO I", 10, 120),
        _record(2, "B", "2026-01-03", "SUSCR.POR TRASPASO I", 12, 120),
    ]
    history = {
        "A": {"2026-01-01": 10, "2026-01-02": 12, "2026-01-03": 12},
        "B": {"2026-01-01": 10, "2026-01-02": 10, "2026-01-03": 10},
    }

    source = calculate_investment_performance(records=rows, histories=history, account_id=1)
    destination = calculate_investment_performance(records=rows, histories=history, account_id=2)
    household = calculate_investment_performance(records=rows, histories=history)

    assert source[-1]["valor"] == 0.0
    assert source[-1]["pnl"] == 20.0
    assert destination[-1]["valor"] == 120.0
    assert destination[-1]["pnl"] == 0.0
    assert household[-1]["valor"] == 120.0
    assert household[-1]["pnl"] == 20.0


def test_missing_instrument_history_does_not_hide_available_assets() -> None:
    rows = [
        _record(1, "A", "2026-01-01", "Compra", 1, 100, kind="stock"),
        _record(1, "MISSING", "2026-01-01", "Compra", 1, 50, kind="stock"),
    ]

    result = calculate_investment_performance(
        records=rows,
        histories={"A": {"2026-01-01": 110}, "MISSING": {}},
        kind="stock",
    )

    assert result[0]["valor"] == 110.0
    assert result[0]["invertido"] == 150.0


def test_staggered_histories_forward_fill_without_using_future_prices() -> None:
    rows = [
        _record(1, "A", "2026-01-01", "Compra", 1, 100, kind="stock"),
        _record(1, "B", "2026-01-02", "Compra", 1, 100, kind="stock"),
    ]

    result = calculate_investment_performance(
        records=rows,
        histories={
            "A": {"2026-01-01": 100, "2026-01-03": 120},
            "B": {"2026-01-02": 100, "2026-01-03": 110},
        },
        kind="stock",
    )

    assert [point["valor"] for point in result] == [100.0, 200.0, 230.0]


def test_unsupported_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported investment kind"):
        calculate_investment_performance([], {}, kind="bond")


@pytest.mark.django_db
def test_canonical_endpoint_serves_all_kinds_and_removes_legacy_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, client = _workspace_client("performance-api")
    fund_account = Account.objects.create(
        workspace=workspace,
        name="Funds",
        kind=Account.Kind.FUNDS,
        currency="EUR",
        external_id="legacy:funds:1",
    )
    rows_by_kind = {
        "fund": [_record(1, "FUND", "2026-01-01", "SUSCRIPCION", 1, 100)],
        "stock": [_record(1, "STOCK", "2026-01-01", "Compra", 1, 100, kind="stock")],
        "crypto": [_record(1, "BTC", "2026-01-01", "Compra", 1, 100, kind="crypto")],
    }
    kind_names = {"fund": "fund", "stock": "stock", "crypto": "crypto"}

    monkeypatch.setattr(
        views,
        "_transaction_calculation_list",
        lambda _request, kind, _selected_account=None: rows_by_kind[kind_names[str(kind)]],
    )
    monkeypatch.setattr(
        views,
        "workspace_instrument",
        lambda _request, _scheme, asset: type(
            "InstrumentStub",
            (),
            {"kind": "crypto" if asset == "BTC" else "fund" if asset == "FUND" else "stock"},
        )(),
    )
    monkeypatch.setattr(views, "yahoo_ticker", lambda instrument: instrument.kind)
    monkeypatch.setattr(
        views,
        "yahoo_chart",
        lambda ticker, **_kwargs: ({"currency": "EUR"}, [{"fecha": "2026-01-01", "precio": 110}]),
    )
    monkeypatch.setattr(
        views,
        "rates_to_base",
        lambda _quote, _base, dates, **_kwargs: {
            value: FxConversion(Decimal("1"), value, "test") for value in dates
        },
    )

    for kind in ("fund", "stock", "crypto"):
        response = client.get(f"/api/investment-performance/{kind}")
        assert response.status_code == 200
        assert set(response.json()) == {"range", "account_id", "base_currency", "data"}
        assert response.json()["base_currency"] == workspace.base_currency
        assert response.json()["data"][0]["value"] == 110.0

    alias = client.get("/api/account-performance")
    assert alias.status_code == 404
    canonical_account = client.get(f"/api/investment-performance/fund?account_id={fund_account.pk}")
    assert canonical_account.status_code == 200
    assert canonical_account.json()["account_id"] == str(fund_account.pk)


@pytest.mark.django_db
def test_performance_rejects_wrong_kind_foreign_accounts_and_invalid_ranges() -> None:
    workspace, client = _workspace_client("performance-isolation")
    stock_account = Account.objects.create(
        workspace=workspace,
        name="Stocks",
        kind=Account.Kind.STOCKS,
        currency="EUR",
        external_id="legacy:stocks:7",
    )
    foreign = Workspace.objects.create(name="Foreign", slug="performance-foreign")
    foreign_account = Account.objects.create(
        workspace=foreign,
        name="Funds",
        kind=Account.Kind.FUNDS,
        currency="EUR",
        external_id="legacy:funds:8",
    )

    wrong_kind = client.get(f"/api/investment-performance/fund?account_id={stock_account.pk}")
    foreign_response = client.get(
        f"/api/investment-performance/fund?account_id={foreign_account.pk}"
    )
    invalid_account = client.get("/api/investment-performance/fund?account_id=not-a-uuid")
    incomplete = client.get("/api/investment-performance/fund?start=2026-01-01")
    reversed_range = client.get("/api/investment-performance/fund?start=2026-02-01&end=2026-01-01")
    invalid_kind = client.get("/api/investment-performance/bond")

    assert wrong_kind.status_code == 404
    assert foreign_response.status_code == 404
    assert invalid_account.status_code == 400
    assert incomplete.status_code == 400
    assert reversed_range.status_code == 400
    assert invalid_kind.status_code == 400


@pytest.mark.django_db
def test_custom_bounds_are_inclusive_and_history_uses_point_date_fx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workspace, client = _workspace_client("performance-custom")
    rows = [_record(1, "FUND", "2026-01-01", "SUSCRIPCION", 1, 100)]
    monkeypatch.setattr(views, "_transaction_calculation_list", lambda *_args: rows)
    monkeypatch.setattr(
        views,
        "workspace_instrument",
        lambda *_args: type("InstrumentStub", (), {"kind": "fund"})(),
    )
    monkeypatch.setattr(views, "yahoo_ticker", lambda _instrument: "FUND")
    monkeypatch.setattr(
        views,
        "yahoo_chart",
        lambda *_args, **_kwargs: (
            {"currency": "USD"},
            [
                {"fecha": "2026-01-01", "precio": 100},
                {"fecha": "2026-02-01", "precio": 110},
                {"fecha": "2026-03-01", "precio": 120},
            ],
        ),
    )
    monkeypatch.setattr(
        views,
        "rates_to_base",
        lambda _quote, _base, dates, **_kwargs: {
            value: FxConversion(
                Decimal("0.9") if value == date(2026, 1, 1) else Decimal("0.8"),
                value,
                "test",
            )
            for value in dates
        },
    )

    response = client.get("/api/investment-performance/fund?start=2026-01-01&end=2026-02-01")

    assert response.status_code == 200
    assert response.json()["range"] == "2026-01-01_2026-02-01"
    assert response.json()["data"] == [
        {
            "date": "2026-01-01",
            "value": 90.0,
            "invested": 100.0,
            "pnl": -10.0,
            "pnl_percent": -10.0,
        },
        {
            "date": "2026-02-01",
            "value": 88.0,
            "invested": 100.0,
            "pnl": -12.0,
            "pnl_percent": -12.0,
        },
    ]


@pytest.mark.django_db
def test_named_range_bounds_exclude_old_and_future_transactions_but_keep_terminal_sale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workspace, client = _workspace_client("performance-named-bounds")
    rows = [
        _record(1, "FUND", "2025-01-01", "SUSCRIPCION", 1, 100),
        _record(1, "FUND", "2026-08-22", "REEMBOLSO", 1, 130),
        _record(1, "FUND", "2026-08-24", "SUSCRIPCION", 1, 200),
    ]
    monkeypatch.setattr(views.timezone, "localdate", lambda: date(2026, 8, 23))
    monkeypatch.setattr(views, "_transaction_calculation_list", lambda *_args: rows)
    monkeypatch.setattr(
        views,
        "workspace_instrument",
        lambda *_args: type("InstrumentStub", (), {"kind": "fund"})(),
    )
    monkeypatch.setattr(views, "yahoo_ticker", lambda _instrument: "FUND")
    monkeypatch.setattr(
        views,
        "yahoo_chart",
        lambda *_args, **_kwargs: (
            {"currency": "EUR"},
            [{"fecha": "2026-02-24", "precio": 120}],
        ),
    )
    monkeypatch.setattr(
        views,
        "rates_to_base",
        lambda _quote, _base, dates, **_kwargs: {
            value: FxConversion(Decimal("1"), value, "test") for value in dates
        },
    )

    response = client.get("/api/investment-performance/fund?range=6m")

    assert response.status_code == 200
    assert [point["date"] for point in response.json()["data"]] == [
        "2026-02-24",
        "2026-08-22",
    ]
    assert response.json()["data"][-1]["value"] == 0.0
    assert response.json()["data"][-1]["pnl"] == 30.0


@pytest.mark.django_db
def test_transient_history_failure_does_not_warm_aggregate_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workspace, client = _workspace_client("performance-failure")
    rows = [_record(1, "FUND", "2026-01-01", "SUSCRIPCION", 1, 100)]
    calls: list[int] = []
    monkeypatch.setattr(views, "_transaction_calculation_list", lambda *_args: rows)
    monkeypatch.setattr(
        views,
        "workspace_instrument",
        lambda *_args: type("InstrumentStub", (), {"kind": "fund"})(),
    )
    monkeypatch.setattr(views, "yahoo_ticker", lambda _instrument: "FUND")

    def chart(*_args: object, **_kwargs: object) -> tuple[dict[str, str], list[dict[str, object]]]:
        calls.append(1)
        if len(calls) == 1:
            raise views.MarketDataError("temporary")
        return {"currency": "EUR"}, [{"fecha": "2026-01-01", "precio": 110}]

    monkeypatch.setattr(views, "yahoo_chart", chart)
    monkeypatch.setattr(
        views,
        "rates_to_base",
        lambda _quote, _base, dates, **_kwargs: {
            value: FxConversion(Decimal("1"), value, "test") for value in dates
        },
    )

    first = client.get("/api/investment-performance/fund")
    second = client.get("/api/investment-performance/fund")

    assert first.json()["data"] == []
    assert second.json()["data"][0]["value"] == 110.0
    assert len(calls) == 2


@pytest.mark.django_db
def test_transient_ticker_discovery_failure_does_not_warm_aggregate_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workspace, client = _workspace_client("performance-ticker-failure")
    rows = [_record(1, "FUND", "2026-01-01", "SUSCRIPCION", 1, 100)]
    discoveries: list[int] = []
    monkeypatch.setattr(views, "_transaction_calculation_list", lambda *_args: rows)

    def instrument(*_args: object) -> object:
        discoveries.append(1)
        if len(discoveries) == 1:
            raise views.MarketDataError("temporary ticker failure")
        return type("InstrumentStub", (), {"kind": "fund"})()

    monkeypatch.setattr(views, "workspace_instrument", instrument)
    monkeypatch.setattr(views, "yahoo_ticker", lambda _instrument: "FUND")
    monkeypatch.setattr(
        views,
        "yahoo_chart",
        lambda *_args, **_kwargs: ({"currency": "EUR"}, [{"fecha": "2026-01-01", "precio": 110}]),
    )
    monkeypatch.setattr(
        views,
        "rates_to_base",
        lambda _quote, _base, dates, **_kwargs: {
            value: FxConversion(Decimal("1"), value, "test") for value in dates
        },
    )

    first = client.get("/api/investment-performance/fund")
    second = client.get("/api/investment-performance/fund")

    assert first.json()["data"] == []
    assert second.json()["data"][0]["value"] == 110.0
    assert len(discoveries) == 2


@pytest.mark.django_db
def test_stock_split_mutation_invalidates_performance_cache() -> None:
    workspace, client = _workspace_client("performance-split-cache")
    instrument = Instrument.objects.create(kind="stock", name="Stock", quote_currency="EUR")
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value="STOCK",
        is_primary=True,
    )
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=instrument)
    cache_key = f"investment-performance:v2:{workspace.pk}:stock:all:1y:EUR:saveback=0"
    cache.set(cache_key, {"data": ["stale"]}, timeout=3600)

    response = client.post(
        "/api/stock-splits",
        {
            "instrument_id": str(instrument.pk),
            "effective_date": "2026-02-01",
            "ratio": 2,
        },
        format="json",
    )

    assert response.status_code == 200
    assert cache.get(cache_key) is None
    cache.set(cache_key, {"data": ["stale"]}, timeout=3600)
    split_id = response.json()["id"]
    deleted = client.delete(f"/api/stock-splits/{split_id}")
    assert deleted.status_code == 200
    assert cache.get(cache_key) is None
