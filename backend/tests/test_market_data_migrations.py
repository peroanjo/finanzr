from datetime import date
from decimal import Decimal
from importlib import import_module

import pytest
from apps.accounts.models import Account
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    StockSplit,
    WorkspaceInstrument,
)
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient

migration = import_module("apps.market_data.migrations.0010_seed_byd_stock_split")
BYD_EFFECTIVE_DATE = migration.BYD_EFFECTIVE_DATE
BYD_ISIN = migration.BYD_ISIN
BYD_RATIO = migration.BYD_RATIO
BYD_SOURCE = migration.BYD_SOURCE
reverse_byd_stock_split = migration.reverse_byd_stock_split
seed_byd_stock_split = migration.seed_byd_stock_split


@pytest.mark.django_db
def test_seed_byd_split_is_workspace_scoped_idempotent_and_non_destructive(
    api_session: tuple[APIClient, User],
) -> None:
    _client, user = api_session
    linked_workspace = user.memberships.get().workspace
    transaction_workspace = Workspace.objects.create(
        name="Synthetic transaction workspace",
        slug="synthetic-byd-transaction",
    )
    unrelated_workspace = Workspace.objects.create(
        name="Synthetic unrelated workspace",
        slug="synthetic-byd-unrelated",
    )
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="Synthetic canonical BYD",
        quote_currency="EUR",
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value=BYD_ISIN,
        venue="",
        is_primary=True,
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value=BYD_ISIN,
        venue="other-venue",
    )
    WorkspaceInstrument.objects.create(workspace=linked_workspace, instrument=instrument)

    account = Account.objects.create(
        workspace=transaction_workspace,
        name="Synthetic stock account",
        kind=Account.Kind.STOCKS,
        currency="EUR",
    )
    Transaction.objects.create(
        account=account,
        instrument=instrument,
        trade_date=date(2025, 1, 2),
        operation_type=Transaction.OperationType.BUY,
        quantity=Decimal("1"),
        unit_price=Decimal("10"),
        net_amount=Decimal("10"),
        fee=Decimal("0"),
    )
    manual = StockSplit.objects.create(
        workspace=linked_workspace,
        instrument=instrument,
        effective_date=BYD_EFFECTIVE_DATE,
        ratio=Decimal("4"),
        source="manual-user-edit",
    )

    seed_byd_stock_split(apps, None)
    seed_byd_stock_split(apps, None)

    assert StockSplit.objects.get(pk=manual.pk).ratio == Decimal("4")
    assert StockSplit.objects.get(pk=manual.pk).source == "manual-user-edit"
    seeded = StockSplit.objects.get(
        workspace=transaction_workspace,
        instrument=instrument,
        effective_date=BYD_EFFECTIVE_DATE,
    )
    assert seeded.ratio == BYD_RATIO
    assert seeded.source == BYD_SOURCE
    assert (
        StockSplit.objects.filter(
            workspace=unrelated_workspace,
            instrument=instrument,
        ).count()
        == 0
    )

    reverse_byd_stock_split(apps, None)
    assert StockSplit.objects.filter(pk=manual.pk).exists()
    assert StockSplit.objects.filter(pk=seeded.pk).exists()


@pytest.mark.django_db
def test_seed_byd_split_excludes_non_default_venue_and_wrong_kind(
    api_session: tuple[APIClient, User],
) -> None:
    _client, user = api_session
    workspace = user.memberships.get().workspace
    non_default_stock = Instrument.objects.create(
        kind=Instrument.Kind.STOCK,
        name="Synthetic non-default venue stock",
        quote_currency="EUR",
    )
    InstrumentIdentifier.objects.create(
        instrument=non_default_stock,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value=BYD_ISIN,
        venue="synthetic-venue",
    )
    wrong_kind = Instrument.objects.create(
        kind=Instrument.Kind.FUND,
        name="Synthetic wrong-kind BYD",
        quote_currency="EUR",
    )
    InstrumentIdentifier.objects.create(
        instrument=wrong_kind,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value=BYD_ISIN,
        venue="",
    )
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=non_default_stock)
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=wrong_kind)

    seed_byd_stock_split(apps, None)

    assert not StockSplit.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db(transaction=True)
def test_seed_byd_split_runs_against_pre_0010_historical_models() -> None:
    executor = MigrationExecutor(connection)
    pre_migration = ("market_data", "0009_native_market_prices")
    executor.migrate([pre_migration])
    try:
        historical_apps = executor.loader.project_state([pre_migration]).apps
        Workspace = historical_apps.get_model("workspaces", "Workspace")
        Instrument = historical_apps.get_model("market_data", "Instrument")
        InstrumentIdentifier = historical_apps.get_model("market_data", "InstrumentIdentifier")
        WorkspaceInstrument = historical_apps.get_model("market_data", "WorkspaceInstrument")

        workspace = Workspace.objects.create(
            name="Synthetic historical workspace",
            slug="synthetic-byd-historical",
        )
        canonical = Instrument.objects.create(
            kind="stock",
            name="Synthetic historical canonical stock",
            base_currency="EUR",
        )
        InstrumentIdentifier.objects.create(
            instrument=canonical,
            scheme="isin",
            value=BYD_ISIN,
            venue="",
        )
        non_default = Instrument.objects.create(
            kind="stock",
            name="Synthetic historical non-default stock",
            base_currency="EUR",
        )
        InstrumentIdentifier.objects.create(
            instrument=non_default,
            scheme="isin",
            value=BYD_ISIN,
            venue="synthetic-venue",
        )
        wrong_kind = Instrument.objects.create(
            kind="fund",
            name="Synthetic historical wrong-kind fund",
            base_currency="EUR",
        )
        InstrumentIdentifier.objects.create(
            instrument=wrong_kind,
            scheme="isin",
            value=BYD_ISIN,
            venue="synthetic-kind-venue",
        )
        WorkspaceInstrument.objects.create(workspace=workspace, instrument=canonical)
        WorkspaceInstrument.objects.create(workspace=workspace, instrument=non_default)
        WorkspaceInstrument.objects.create(workspace=workspace, instrument=wrong_kind)

        executor = MigrationExecutor(connection)
        executor.migrate([("market_data", "0010_seed_byd_stock_split")])
        assert (
            StockSplit.objects.filter(
                workspace_id=workspace.pk,
                instrument_id=canonical.pk,
                effective_date=BYD_EFFECTIVE_DATE,
            ).count()
            == 1
        )
        assert not StockSplit.objects.filter(
            workspace_id=workspace.pk,
            instrument_id=non_default.pk,
        ).exists()
        assert not StockSplit.objects.filter(
            workspace_id=workspace.pk,
            instrument_id=wrong_kind.pk,
        ).exists()
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
