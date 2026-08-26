from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from apps.accounts.models import Account
from apps.market_data import fx
from apps.market_data.models import FxRate
from apps.transactions.currency import conversion_snapshot
from apps.workspaces.models import Workspace


@pytest.mark.django_db
def test_historical_fx_rates_are_cached_and_use_the_requested_market_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_chart(*_args: Any, **_kwargs: Any) -> tuple[dict[str, str], list[dict[str, object]]]:
        return (
            {"currency": "EUR"},
            [
                {"fecha": "2026-01-02", "precio": 0.91},
                {"fecha": "2026-01-05", "precio": 0.92},
            ],
        )

    monkeypatch.setattr(fx, "yahoo_chart", fake_chart)

    result = fx.rates_to_base(
        "USD",
        "EUR",
        [date(2026, 1, 2), date(2026, 1, 5)],
    )

    assert result[date(2026, 1, 2)].rate == Decimal("0.91")
    assert result[date(2026, 1, 5)].rate == Decimal("0.92")
    assert FxRate.objects.count() == 2


@pytest.mark.django_db
def test_transaction_snapshot_keeps_original_amount_and_normalizes_to_workspace_currency() -> None:
    workspace = Workspace.objects.create(name="Test", slug="currency-test", base_currency="EUR")
    account = Account.objects.create(
        workspace=workspace,
        name="USD broker",
        kind=Account.Kind.FUNDS,
        currency="USD",
    )
    FxRate.objects.create(
        quote_currency="USD",
        base_currency="EUR",
        rate_date=date(2026, 1, 10),
        rate=Decimal("0.9"),
        source="test",
    )

    snapshot = conversion_snapshot(
        account=account,
        currency="USD",
        trade_date=date(2026, 1, 10),
        settlement_date=None,
        unit_price=Decimal("10"),
        net_amount=Decimal("100"),
        fee=Decimal("1"),
    )

    assert snapshot["base_currency"] == "EUR"
    assert snapshot["base_net_amount"] == Decimal("90.0")
    assert snapshot["base_unit_price"] == Decimal("9.0")
    assert snapshot["base_fee"] == Decimal("0.9")
    assert snapshot["fx_rate_date"] == date(2026, 1, 10)
