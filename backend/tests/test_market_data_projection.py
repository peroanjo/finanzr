from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from apps.accounts.models import Account
from apps.api import analysis_views, overview_queries, performance_views
from apps.api.market_data_projection import stock_split_calculation_rows
from apps.market_data.fx import FxConversion
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    StockSplit,
    WorkspaceInstrument,
)
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace
from django.core.cache import cache
from rest_framework.test import APIClient

from finanzr.domain.stocks import calculate_stock_positions


@pytest.mark.django_db
def test_stock_split_calculation_rows_project_canonical_isin_and_multiple_splits() -> None:
    workspace = Workspace.objects.create(
        name="Synthetic split projection",
        slug="synthetic-split-projection",
        base_currency="EUR",
    )
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="Synthetic split stock",
        quote_currency="EUR",
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value="SYNTHETIC-ALT",
        venue="alternate-venue",
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value="SYNTHETIC-CANONICAL",
        venue="",
    )
    StockSplit.objects.create(
        workspace=workspace,
        instrument=instrument,
        effective_date=date(2026, 2, 1),
        ratio=Decimal("3"),
        source="synthetic-later",
    )
    StockSplit.objects.create(
        workspace=workspace,
        instrument=instrument,
        effective_date=date(2026, 1, 1),
        ratio=Decimal("2.5"),
        source="synthetic-earlier",
    )

    rows = stock_split_calculation_rows(
        StockSplit.objects.filter(workspace=workspace, instrument=instrument)
        .select_related("instrument")
        .prefetch_related("instrument__identifiers")
    )

    assert rows == [
        {"isin": "SYNTHETIC-CANONICAL", "fecha": "2026-02-01", "ratio": 3.0},
        {"isin": "SYNTHETIC-CANONICAL", "fecha": "2026-01-01", "ratio": 2.5},
    ]


@pytest.mark.django_db
def test_stock_split_calculation_rows_preserve_blank_identity_for_legacy_consumers() -> None:
    workspace = Workspace.objects.create(
        name="Synthetic blank split projection",
        slug="synthetic-blank-split-projection",
        base_currency="EUR",
    )
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="Synthetic identifierless stock",
        quote_currency="EUR",
    )
    StockSplit.objects.create(
        workspace=workspace,
        instrument=instrument,
        effective_date=date(2026, 2, 1),
        ratio=Decimal("2"),
        source="synthetic-blank-identity",
    )

    rows = stock_split_calculation_rows(
        StockSplit.objects.filter(workspace=workspace, instrument=instrument)
        .select_related("instrument")
        .prefetch_related("instrument__identifiers")
    )
    positions = calculate_stock_positions(
        [
            {
                "isin": "",
                "fecha_operacion": "2026-01-01",
                "titulos": 2,
                "importe_base": 20,
                "tipo_operacion": "Compra",
            }
        ],
        {},
        rows,
    )

    assert rows == [{"isin": "", "fecha": "2026-02-01", "ratio": 2.0}]
    assert positions[0]["titulos"] == 4.0
    assert positions[0]["coste_total"] == 20.0


@pytest.mark.django_db
def test_stock_split_calculation_rows_keep_workspace_and_instrument_filters_explicit() -> None:
    workspace = Workspace.objects.create(
        name="Synthetic split scope",
        slug="synthetic-split-scope",
        base_currency="EUR",
    )
    foreign_workspace = Workspace.objects.create(
        name="Synthetic foreign split scope",
        slug="synthetic-foreign-split-scope",
        base_currency="EUR",
    )
    visible_instrument = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="Synthetic visible stock",
        quote_currency="EUR",
    )
    hidden_instrument = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="Synthetic hidden stock",
        quote_currency="EUR",
    )
    for instrument, value in (
        (visible_instrument, "SYNTHETIC-VISIBLE"),
        (hidden_instrument, "SYNTHETIC-HIDDEN"),
    ):
        InstrumentIdentifier.objects.create(
            instrument=instrument,
            scheme=InstrumentIdentifier.Scheme.ISIN,
            value=value,
            venue="",
        )
    StockSplit.objects.create(
        workspace=workspace,
        instrument=visible_instrument,
        effective_date=date(2026, 1, 1),
        ratio=Decimal("2"),
        source="synthetic-visible",
    )
    StockSplit.objects.create(
        workspace=workspace,
        instrument=hidden_instrument,
        effective_date=date(2026, 1, 1),
        ratio=Decimal("5"),
        source="synthetic-wrong-instrument",
    )
    StockSplit.objects.create(
        workspace=foreign_workspace,
        instrument=visible_instrument,
        effective_date=date(2026, 1, 1),
        ratio=Decimal("7"),
        source="synthetic-foreign-workspace",
    )

    rows = stock_split_calculation_rows(
        StockSplit.objects.filter(workspace=workspace, instrument_id=visible_instrument.id)
        .select_related("instrument")
        .prefetch_related("instrument__identifiers")
    )

    assert rows == [{"isin": "SYNTHETIC-VISIBLE", "fecha": "2026-01-01", "ratio": 2.0}]


@pytest.mark.django_db
def test_analysis_passes_identifierless_split_to_stock_calculator(
    api_session: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, user = api_session
    workspace = user.memberships.get().workspace
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="Synthetic analysis identifierless stock",
        quote_currency="EUR",
    )
    StockSplit.objects.create(
        workspace=workspace,
        instrument=instrument,
        effective_date=date(2026, 2, 1),
        ratio=Decimal("2"),
        source="synthetic-analysis-blank",
    )
    projected: list[list[dict[str, Any]]] = []

    def capture_analysis(
        _rows: Any, _prices: Any, splits: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        projected.append(splits)
        return []

    monkeypatch.setattr(
        analysis_views,
        "calculate_stock_positions",
        capture_analysis,
    )

    response = client.get("/api/stock-analysis")

    assert response.status_code == 200
    assert projected == [[{"isin": "", "fecha": "2026-02-01", "ratio": 2.0}]]


@pytest.mark.django_db
def test_overview_passes_identifierless_split_to_stock_calculator(
    api_session: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, user = api_session
    workspace = user.memberships.get().workspace
    account = Account.objects.create(
        workspace=workspace,
        name="Synthetic overview stocks",
        kind=Account.Kind.STOCKS,
        currency="EUR",
    )
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="Synthetic overview identifierless stock",
        quote_currency="EUR",
    )
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=instrument)
    Transaction.objects.create(
        account=account,
        instrument=instrument,
        trade_date=date(2026, 3, 1),
        operation_type=Transaction.OperationType.BUY,
        cash_flow_type=Transaction.CashFlowType.CONTRIBUTION,
        quantity=2,
        unit_price=10,
        net_amount=20,
        fee=0,
        currency="EUR",
        base_currency="EUR",
        base_unit_price=10,
        base_net_amount=20,
        base_fee=0,
    )
    StockSplit.objects.create(
        workspace=workspace,
        instrument=instrument,
        effective_date=date(2026, 2, 1),
        ratio=Decimal("2"),
        source="synthetic-overview-blank",
    )
    projected: list[list[dict[str, Any]]] = []

    def capture_overview(
        _rows: Any, _prices: Any, splits: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        projected.append(splits)
        return []

    monkeypatch.setattr(
        overview_queries,
        "calculate_stock_positions",
        capture_overview,
    )
    monkeypatch.setattr(
        overview_queries,
        "effective_summary_sources",
        lambda *_args: (["stocks"], "synthetic"),
    )

    assert stock_split_calculation_rows(
        StockSplit.objects.filter(workspace=workspace, instrument=instrument)
    ) == [{"isin": "", "fecha": "2026-02-01", "ratio": 2.0}]

    response = client.get("/api/net-worth-history")

    assert response.status_code == 200
    assert projected == [[{"isin": "", "fecha": "2026-02-01", "ratio": 2.0}]]


@pytest.mark.django_db
def test_performance_ignores_identifierless_split_rows(
    api_session: tuple[APIClient, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, user = api_session
    workspace = user.memberships.get().workspace
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="Synthetic performance identifierless stock",
        quote_currency="EUR",
    )
    StockSplit.objects.create(
        workspace=workspace,
        instrument=instrument,
        effective_date=date(2026, 2, 1),
        ratio=Decimal("2"),
        source="synthetic-performance-blank",
    )
    cache.clear()
    projected: list[list[dict[str, Any]]] = []

    def capture_performance(_rows: Any, _histories: Any, **kwargs: Any) -> list[dict[str, Any]]:
        projected.append(kwargs["splits"])
        return []

    monkeypatch.setattr(
        performance_views,
        "transaction_calculation_rows",
        lambda *_args: [{"isin": "SYNTHETIC-PERFORMANCE", "fecha_operacion": "2026-01-01"}],
    )
    monkeypatch.setattr(
        performance_views,
        "workspace_instrument",
        lambda *_args: type("SyntheticInstrument", (), {"kind": Instrument.Kind.STOCK})(),
    )
    monkeypatch.setattr(performance_views, "yahoo_ticker", lambda _instrument: "SYNTHETIC")
    monkeypatch.setattr(
        performance_views,
        "yahoo_chart",
        lambda *_args, **_kwargs: (
            {"currency": "EUR"},
            [{"fecha": "2026-01-01", "precio": 10}],
        ),
    )
    monkeypatch.setattr(
        performance_views,
        "rates_to_base",
        lambda _quote, _base, dates, **_kwargs: {
            requested_date: FxConversion(Decimal("1"), requested_date, "synthetic")
            for requested_date in dates
        },
    )
    monkeypatch.setattr(
        performance_views,
        "calculate_investment_performance",
        capture_performance,
    )

    response = client.get("/api/investment-performance/stock")

    assert response.status_code == 200
    assert response.json()["data"] == []
    assert projected == [[]]
