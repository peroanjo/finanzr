from datetime import UTC, date, datetime
from decimal import Decimal
from typing import NoReturn

import pytest
from apps.accounts.models import Account, AccountSnapshot
from apps.api import overview_queries
from apps.api.transaction_projection import transaction_row
from apps.common.models import InstallationSettings, SummaryPreference
from apps.common.summary_preferences import effective_summary_sources
from apps.market_data.fx import CurrencyConversionError, FxConversion
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    MarketPrice,
    WorkspaceInstrument,
)
from apps.portfolio.models import ManualAsset
from apps.real_estate.models import RealEstateCashFlow, RealEstateInvestment
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from rest_framework.test import APIClient


def setup_workspace() -> tuple[Workspace, User, User]:
    workspace = Workspace.objects.create(name="Casa", slug="summary-casa")
    first = User.objects.create_user(email="summary-one@example.com", password="a-safe-password")
    second = User.objects.create_user(email="summary-two@example.com", password="a-safe-password")
    WorkspaceMembership.objects.create(workspace=workspace, user=first, role="owner")
    WorkspaceMembership.objects.create(workspace=workspace, user=second, role="viewer")
    account = Account.objects.create(
        workspace=workspace,
        name="Cuenta corriente",
        kind=Account.Kind.SAVINGS,
        external_id="legacy:savings:1",
    )
    AccountSnapshot.objects.create(
        account=account,
        date=date(2026, 7, 31),
        value=100,
        contribution=100,
        earnings=0,
    )
    ManualAsset.objects.create(
        workspace=workspace,
        name="Colección",
        asset_class="Alternativos",
        value=40,
        currency="EUR",
        valued_at=date(2026, 7, 31),
    )
    return workspace, first, second


@pytest.mark.django_db
def test_summary_defaults_are_legacy_and_personal_sources_change_summary_and_history() -> None:
    workspace, user, other_user = setup_workspace()
    client = APIClient()
    client.force_authenticate(user)

    initial = client.get("/api/summary").json()
    assert initial["summary_sources"] == ["savings", "manual_investments", "crowdfunding"]
    assert initial["net_worth"] == 100
    assert initial["total_savings"] == 100
    assert initial["source_breakdown"][-1] == {
        "key": "manual_assets",
        "value": 0,
        "included": False,
    }

    saved = client.patch(
        "/api/auth/preferences",
        {"summary_sources": ["manual_assets"]},
        format="json",
    )
    assert saved.status_code == 200
    assert saved.json()["summary_sources"] == ["manual_assets"]
    assert saved.json()["summary_sources_scope"] == "personal"
    assert SummaryPreference.objects.get(user=user, workspace=workspace).included_sources == [
        "manual_assets"
    ]

    changed = client.get("/api/summary").json()
    assert changed["net_worth"] == 40
    assert changed["total_savings"] == 0
    history = client.get("/api/net-worth-history").json()
    assert history[-1]["total"] == 40
    assert history[-1]["source_totals"]["manual_assets"] == 40

    client.force_authenticate(other_user)
    assert client.get("/api/summary").json()["summary_sources"] == [
        "savings",
        "manual_investments",
        "crowdfunding",
    ]
    assert client.get("/api/summary").json()["net_worth"] == 100


@pytest.mark.django_db
def test_summary_sources_are_validated_atomically_and_isolated_by_workspace() -> None:
    workspace, user, _other_user = setup_workspace()
    second_workspace = Workspace.objects.create(name="Trabajo", slug="summary-trabajo")
    WorkspaceMembership.objects.create(workspace=second_workspace, user=user, role="owner")
    client = APIClient()
    client.force_authenticate(user)

    invalid = client.patch(
        "/api/auth/preferences",
        {"summary_sources": ["savings", "not-a-source"]},
        format="json",
    )
    assert invalid.status_code == 400
    assert client.get("/api/summary").json()["summary_sources"] == [
        "savings",
        "manual_investments",
        "crowdfunding",
    ]

    changed = client.patch("/api/auth/preferences", {"summary_sources": []}, format="json")
    assert changed.status_code == 200
    assert changed.json()["summary_sources"] == []

    selected = client.put(
        "/api/workspaces/current",
        {"workspace_id": str(second_workspace.id)},
        format="json",
    )
    assert selected.status_code == 200
    assert selected.json()["summary_sources"] == ["savings", "manual_investments", "crowdfunding"]

    back = client.put("/api/workspaces/current", {"workspace_id": str(workspace.id)}, format="json")
    assert back.status_code == 200
    assert back.json()["summary_sources"] == []

    reset = client.patch("/api/auth/preferences", {"summary_sources": None}, format="json")
    assert reset.status_code == 200
    assert reset.json()["summary_sources"] == ["savings", "manual_investments", "crowdfunding"]
    assert reset.json()["summary_sources_scope"] == "installation"


@pytest.mark.django_db
def test_fund_source_uses_current_stored_market_value_in_summary_and_history() -> None:
    workspace, user, _other_user = setup_workspace()
    account = Account.objects.create(
        workspace=workspace,
        name="Fondos",
        kind=Account.Kind.FUNDS,
        external_id="legacy:funds:1",
    )
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.FUND,
        name="Fondo global",
        quote_currency="EUR",
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value="IE000FUND000",
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.YAHOO,
        value="FUND-EUR",
    )
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=instrument)
    Transaction.objects.create(
        account=account,
        instrument=instrument,
        trade_date=date(2026, 7, 31),
        operation_type=Transaction.OperationType.BUY,
        cash_flow_type=Transaction.CashFlowType.CONTRIBUTION,
        quantity=2,
        unit_price=10,
        net_amount=20,
        currency="EUR",
        provider_operation_type="SUSCRIPCION",
    )
    MarketPrice.objects.create(
        instrument=instrument,
        quoted_at=datetime(2026, 7, 31, tzinfo=UTC),
        granularity=MarketPrice.Granularity.SPOT,
        close=12,
        currency="EUR",
        source="test",
    )
    client = APIClient()
    client.force_authenticate(user)
    saved = client.patch("/api/auth/preferences", {"summary_sources": ["funds"]}, format="json")
    assert saved.status_code == 200
    assert client.get("/api/summary").json()["net_worth"] == 24
    history = client.get("/api/net-worth-history").json()
    assert history[-1]["total"] == 24
    assert history[-1]["source_totals"]["funds"] == 24


@pytest.mark.django_db
def test_crowdfunding_only_history_uses_project_and_cashflow_months() -> None:
    workspace, user, _other_user = setup_workspace()
    project = RealEstateInvestment.objects.create(
        workspace=workspace,
        name="Proyecto Norte",
        start_date=date(2026, 1, 15),
        currency="EUR",
    )
    RealEstateCashFlow.objects.create(
        investment=project,
        effective_date=date(2026, 1, 15),
        flow_type=RealEstateCashFlow.FlowType.CONTRIBUTION,
        amount=300,
        is_external=True,
    )
    RealEstateCashFlow.objects.create(
        investment=project,
        effective_date=date(2026, 3, 15),
        flow_type=RealEstateCashFlow.FlowType.CAPITAL_RETURN,
        amount=100,
        is_external=True,
    )
    client = APIClient()
    client.force_authenticate(user)
    assert (
        client.patch(
            "/api/auth/preferences", {"summary_sources": ["crowdfunding"]}, format="json"
        ).status_code
        == 200
    )

    history = client.get("/api/net-worth-history").json()
    assert [point["fecha"] for point in history] == ["2026-01", "2026-03"]
    assert [point["total"] for point in history] == [300, 200]


@pytest.mark.django_db
def test_manual_asset_deduplication_requires_project_correlation() -> None:
    workspace, user, _other_user = setup_workspace()
    project = RealEstateInvestment.objects.create(
        workspace=workspace,
        name="Proyecto Norte",
        start_date=date(2026, 7, 1),
        currency="EUR",
    )
    RealEstateCashFlow.objects.create(
        investment=project,
        effective_date=date(2026, 7, 1),
        flow_type=RealEstateCashFlow.FlowType.CONTRIBUTION,
        amount=300,
        is_external=True,
    )
    # This exact-name/value row is the known historical duplication.
    ManualAsset.objects.create(
        workspace=workspace,
        name="Proyecto Norte",
        asset_class="Other",
        value=300,
        currency="EUR",
        valued_at=date(2026, 7, 31),
    )
    # A property-like label alone is not proof of a duplicate.
    ManualAsset.objects.create(
        workspace=workspace,
        name="Mi inmobiliario privado",
        asset_class="Real estate",
        value=50,
        currency="EUR",
        valued_at=date(2026, 7, 31),
    )
    client = APIClient()
    client.force_authenticate(user)
    assert (
        client.patch(
            "/api/auth/preferences",
            {"summary_sources": ["crowdfunding", "manual_assets"]},
            format="json",
        ).status_code
        == 200
    )
    assert client.get("/api/summary").json()["net_worth"] == 390


@pytest.mark.django_db
def test_corrupt_personal_preference_falls_back_to_installation_sources() -> None:
    workspace, user, _other_user = setup_workspace()
    installation = InstallationSettings.load()
    installation.default_summary_sources = ["manual_assets"]
    installation.save(update_fields=["default_summary_sources"])
    SummaryPreference.objects.create(
        user=user, workspace=workspace, included_sources={"corrupt": True}
    )
    client = APIClient()
    client.force_authenticate(user)
    summary = client.get("/api/summary").json()
    assert summary["summary_sources"] == ["manual_assets"]
    assert summary["summary_sources_scope"] == "installation"
    assert effective_summary_sources(user, workspace) == (["manual_assets"], "installation")


@pytest.mark.django_db
def test_missing_stock_and_crypto_prices_use_open_cost_instead_of_zero() -> None:
    workspace, user, _other_user = setup_workspace()
    stock_account = Account.objects.create(
        workspace=workspace,
        name="Broker",
        kind=Account.Kind.STOCKS,
        external_id="legacy:stocks:1",
    )
    crypto_account = Account.objects.create(
        workspace=workspace,
        name="Exchange",
        kind=Account.Kind.CRYPTO,
        external_id="legacy:crypto:1",
    )
    stock = Instrument.objects.create(
        kind=Instrument.Kind.STOCK, name="Stock", quote_currency="EUR"
    )
    crypto = Instrument.objects.create(
        kind=Instrument.Kind.CRYPTO, name="Bitcoin", quote_currency="EUR"
    )
    InstrumentIdentifier.objects.create(
        instrument=stock, scheme=InstrumentIdentifier.Scheme.ISIN, value="IE-STOCK"
    )
    InstrumentIdentifier.objects.create(
        instrument=crypto, scheme=InstrumentIdentifier.Scheme.CRYPTO_SYMBOL, value="BTC"
    )
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=stock)
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=crypto)
    for account, instrument, amount in ((stock_account, stock, 100), (crypto_account, crypto, 50)):
        Transaction.objects.create(
            account=account,
            instrument=instrument,
            trade_date=date(2026, 7, 31),
            operation_type=Transaction.OperationType.BUY,
            cash_flow_type=Transaction.CashFlowType.CONTRIBUTION,
            quantity=1,
            unit_price=amount,
            net_amount=amount,
            currency="EUR",
        )
    client = APIClient()
    client.force_authenticate(user)
    assert (
        client.patch(
            "/api/auth/preferences",
            {"summary_sources": ["stocks", "crypto"]},
            format="json",
        ).status_code
        == 200
    )
    summary = client.get("/api/summary").json()
    assert summary["net_worth"] == 150
    history = client.get("/api/net-worth-history").json()
    assert history[-1]["source_totals"]["stocks"] == 100
    assert history[-1]["source_totals"]["crypto"] == 50


@pytest.mark.django_db
def test_foreign_transaction_with_resolvable_fx_uses_base_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, user, _other_user = setup_workspace()
    account = Account.objects.create(
        workspace=workspace,
        name="Broker USD",
        kind=Account.Kind.STOCKS,
        external_id="legacy:stocks:2",
    )
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="US stock",
        quote_currency="USD",
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value="US-RESOLVED-FX",
    )
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=instrument)
    Transaction.objects.create(
        account=account,
        instrument=instrument,
        trade_date=date(2026, 1, 31),
        operation_type=Transaction.OperationType.BUY,
        cash_flow_type=Transaction.CashFlowType.CONTRIBUTION,
        quantity=1,
        unit_price=100,
        net_amount=100,
        currency="USD",
        base_currency="EUR",
    )
    monkeypatch.setattr(
        overview_queries,
        "rate_to_base",
        lambda _quote, _base, requested_date, **_kwargs: FxConversion(
            Decimal("0.9"), requested_date, "test"
        ),
    )
    client = APIClient()
    client.force_authenticate(user)
    assert (
        client.patch(
            "/api/auth/preferences", {"summary_sources": ["stocks"]}, format="json"
        ).status_code
        == 200
    )

    history = client.get("/api/net-worth-history").json()
    assert history[-1]["total"] == 90
    assert history[-1]["source_contributions"]["stocks"] == 90


@pytest.mark.django_db
def test_unresolved_foreign_fx_is_not_serialized_or_reported_as_zero_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, user, _other_user = setup_workspace()
    account = Account.objects.create(
        workspace=workspace,
        name="Broker USD",
        kind=Account.Kind.STOCKS,
        external_id="legacy:stocks:3",
    )
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="US stock",
        quote_currency="USD",
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value="US-UNRESOLVED-FX",
    )
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=instrument)
    transaction = Transaction.objects.create(
        account=account,
        instrument=instrument,
        trade_date=date(2026, 1, 31),
        operation_type=Transaction.OperationType.BUY,
        cash_flow_type=Transaction.CashFlowType.CONTRIBUTION,
        quantity=1,
        unit_price=100,
        net_amount=100,
        fee=1,
        currency="USD",
        base_currency="EUR",
    )
    MarketPrice.objects.create(
        instrument=instrument,
        quoted_at=datetime(2026, 7, 31, tzinfo=UTC),
        granularity=MarketPrice.Granularity.SPOT,
        close=120,
        currency="EUR",
        source="test",
    )

    row = transaction_row(transaction)
    assert row["base_net_amount"] is None
    assert row["base_unit_price"] is None
    assert row["base_fee"] is None

    def unavailable(*_args: object, **_kwargs: object) -> NoReturn:
        raise CurrencyConversionError("No USD/EUR rate")

    monkeypatch.setattr(overview_queries, "rate_to_base", unavailable)
    client = APIClient()
    client.force_authenticate(user)
    assert (
        client.patch(
            "/api/auth/preferences", {"summary_sources": ["stocks"]}, format="json"
        ).status_code
        == 200
    )
    assert client.get("/api/net-worth-history").json() == []
    assert client.get("/api/summary").json()["net_worth"] == 0


@pytest.mark.django_db
def test_fund_history_uses_settlement_date() -> None:
    workspace, user, _other_user = setup_workspace()
    account = Account.objects.create(
        workspace=workspace,
        name="Settlement fund",
        kind=Account.Kind.FUNDS,
        external_id="legacy:funds:2",
    )
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.FUND,
        name="Settlement fund",
        quote_currency="EUR",
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value="IE-SETTLEMENT",
    )
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=instrument)
    Transaction.objects.create(
        account=account,
        instrument=instrument,
        trade_date=date(2026, 1, 30),
        settlement_date=date(2026, 2, 3),
        operation_type=Transaction.OperationType.BUY,
        cash_flow_type=Transaction.CashFlowType.CONTRIBUTION,
        quantity=2,
        unit_price=10,
        net_amount=20,
        currency="EUR",
        provider_operation_type="SUSCRIPCION",
    )
    client = APIClient()
    client.force_authenticate(user)
    assert (
        client.patch(
            "/api/auth/preferences", {"summary_sources": ["funds"]}, format="json"
        ).status_code
        == 200
    )

    history = client.get("/api/net-worth-history").json()
    assert [point["fecha"] for point in history] == ["2026-02"]
    assert history[0]["total"] == 20
    assert history[0]["source_contributions"]["funds"] == 20


@pytest.mark.django_db
def test_invalid_source_error_is_clean_and_translated() -> None:
    _workspace, user, _other_user = setup_workspace()
    client = APIClient()
    client.force_authenticate(user)
    english = client.patch(
        "/api/auth/preferences",
        {"summary_sources": "not-a-list"},
        format="json",
        HTTP_ACCEPT_LANGUAGE="en",
    )
    assert english.status_code == 400
    assert english.json()["error"] == "Summary sources must be a list"
    assert not english.json()["error"].startswith("[")
    spanish = client.patch(
        "/api/auth/preferences",
        {"summary_sources": "not-a-list"},
        format="json",
        HTTP_ACCEPT_LANGUAGE="es-es",
    )
    assert spanish.status_code == 400
    assert spanish.json()["error"] == "Las fuentes del resumen deben ser una lista"
