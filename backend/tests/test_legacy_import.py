from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from apps.accounts.models import Account, AccountSnapshot
from apps.imports.legacy import FILE_SCHEMAS, LegacyImportError
from apps.imports.legacy_service import LegacyImportService
from apps.market_data.models import Instrument, MarketPrice, StockSplit
from apps.planning.models import AllocationRule, BudgetLine
from apps.real_estate.models import RealEstateInvestment
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership

from .legacy_fixture import write_legacy_fixture


@pytest.fixture
def legacy_data_dir(tmp_path: Path) -> Path:
    return write_legacy_fixture(tmp_path / "legacy-data")


@pytest.mark.django_db(transaction=True)
def test_dry_run_validates_everything_and_rolls_back(legacy_data_dir: Path) -> None:
    report = LegacyImportService(
        data_dir=legacy_data_dir,
        workspace_slug="dry-run",
        owner_email="owner@example.com",
        dry_run=True,
        validate=True,
    ).run()

    assert report.valid is True
    assert set(report.files) == set(FILE_SCHEMAS)
    assert all(check.matches for check in report.checks)
    assert not Workspace.objects.filter(slug="dry-run").exists()


@pytest.mark.django_db(transaction=True)
def test_real_import_is_complete_and_idempotent(legacy_data_dir: Path) -> None:
    first = LegacyImportService(
        data_dir=legacy_data_dir,
        workspace_slug="personal",
        owner_email="owner@example.com",
        validate=True,
    ).run()

    workspace = Workspace.objects.get(slug="personal")
    assert first.valid is True
    assert WorkspaceMembership.objects.filter(
        workspace=workspace, role=WorkspaceMembership.Role.OWNER
    ).exists()
    assert User.objects.get(email="owner@example.com").role == User.Role.ADMIN
    assert Account.objects.filter(workspace=workspace).count() == 5
    assert AccountSnapshot.objects.filter(account__workspace=workspace).count() == 2
    assert Instrument.objects.count() == 3
    assert Transaction.objects.filter(account__workspace=workspace).count() == 3
    assert MarketPrice.objects.count() == 3
    assert StockSplit.objects.filter(workspace=workspace).count() == 1
    assert RealEstateInvestment.objects.filter(workspace=workspace).count() == 1
    assert BudgetLine.objects.filter(workspace=workspace).count() == 1
    assert AllocationRule.objects.filter(workspace=workspace).count() == 1

    second = LegacyImportService(
        data_dir=legacy_data_dir,
        workspace_slug="personal",
        validate=True,
    ).run()

    assert second.valid is True
    assert sum(item.created for item in second.files.values()) == 0
    assert sum(item.updated for item in second.files.values()) == 0
    assert Account.objects.filter(workspace=workspace).count() == 5
    assert AccountSnapshot.objects.filter(account__workspace=workspace).count() == 2
    assert Transaction.objects.filter(account__workspace=workspace).count() == 3


@pytest.mark.django_db(transaction=True)
def test_invalid_row_rolls_back_the_complete_import(tmp_path: Path, legacy_data_dir: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for filename in FILE_SCHEMAS:
        shutil.copyfile(legacy_data_dir / filename, data_dir / filename)
    history = data_dir / "savings_history.csv"
    history.write_text(
        history.read_text(encoding="utf-8").replace(",1000\n", ",not-a-number\n", 1),
        encoding="utf-8",
    )

    with pytest.raises(LegacyImportError, match="saldo is not a decimal number"):
        LegacyImportService(
            data_dir=data_dir,
            workspace_slug="must-rollback",
            owner_email="owner@example.com",
            validate=True,
        ).run()

    assert not Workspace.objects.filter(slug="must-rollback").exists()
    assert Account.objects.count() == 0
