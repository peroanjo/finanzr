from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from apps.accounts.models import Account, AccountSnapshot
from apps.common.models import InstallationSettings
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
from rest_framework.test import APIClient


@pytest.fixture
def api_session() -> tuple[APIClient, User]:
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

    client = APIClient()

    client.force_authenticate(user=user)

    session = client.session

    session["active_workspace_id"] = str(workspace.pk)

    session.save()

    return client, user


@pytest.fixture
def snapshot_context(api_session: tuple[APIClient, User]) -> tuple[APIClient, User]:
    _, user = api_session
    workspace = user.memberships.get().workspace
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

    return api_session


@pytest.fixture
def traded_context(api_session: tuple[APIClient, User]) -> tuple[APIClient, User]:
    _, user = api_session
    workspace = user.memberships.get().workspace
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

    return api_session


@pytest.fixture
def real_estate_context(api_session: tuple[APIClient, User]) -> tuple[APIClient, User]:
    _, user = api_session
    workspace = user.memberships.get().workspace
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

    return api_session


@pytest.fixture
def portfolio_context(api_session: tuple[APIClient, User]) -> tuple[APIClient, User]:
    _, user = api_session
    workspace = user.memberships.get().workspace
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

    return api_session


@pytest.fixture
def api_context(
    snapshot_context: tuple[APIClient, User],
    traded_context: tuple[APIClient, User],
    real_estate_context: tuple[APIClient, User],
    portfolio_context: tuple[APIClient, User],
) -> tuple[APIClient, User]:
    """Seed every domain only for cross-domain integration and export scenarios."""
    client, user = snapshot_context
    workspace = user.memberships.get().workspace
    BudgetLine.objects.create(
        workspace=workspace,
        category="Synthetic needs",
        amount=Decimal("100"),
        currency="EUR",
        line_type="Necesidad",
        sort_order=0,
    )

    return client, user
