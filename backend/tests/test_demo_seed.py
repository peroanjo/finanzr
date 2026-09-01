from decimal import Decimal
from io import StringIO

import pytest
from apps.accounts.models import Account
from apps.audit.models import AuditEvent
from apps.common.management.commands.seed_demo_data import DEMO_PASSWORD
from apps.market_data.models import MarketPrice
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import Workspace
from django.core.management import call_command
from rest_framework.test import APIClient


@pytest.mark.django_db(transaction=True)
def test_seed_demo_data_is_idempotent_and_serves_representative_sections() -> None:
    first_output = StringIO()
    second_output = StringIO()

    call_command("seed_demo_data", stdout=first_output)
    workspace = Workspace.objects.get(slug="demo")
    AuditEvent.objects.create(
        workspace=workspace,
        event_type="demo.test",
        object_type="workspace",
    )
    call_command("seed_demo_data", stdout=second_output)

    assert Workspace.objects.filter(slug="demo").count() == 1
    assert User.objects.filter(email="demo@finanzr.local").count() == 1
    assert User.objects.get(email="demo@finanzr.local").role == User.Role.DEMO
    assert Account.objects.filter(workspace__slug="demo").count() == 9
    assert "demo@finanzr.local" in second_output.getvalue()

    client = APIClient()
    login = client.post(
        "/api/auth/login",
        {"email": "demo@finanzr.local", "password": DEMO_PASSWORD},
        format="json",
    )

    assert login.status_code == 200
    assert login.json()["role"] == "demo"
    assert len(client.get("/api/savings/accounts").json()) == 3
    assert len(client.get("/api/investments/accounts").json()) == 3
    assert len(client.get("/api/fund-analysis").json()) == 4
    assert len(client.get("/api/stock-analysis").json()) == 4
    assert len(client.get("/api/crypto-analysis").json()) == 2
    assert len(client.get("/api/real-estate").json()) == 2
    blocked_write = client.post(
        "/api/savings/accounts",
        {"name": "No persistir", "bank": "Demo", "type": "Current"},
        format="json",
    )
    assert blocked_write.status_code == 403
    assert blocked_write.json()["detail"] == "La cuenta demo es de solo lectura"

    summary = client.get("/api/summary").json()
    portfolio = client.get("/api/portfolio-analysis").json()
    assert summary["total_savings"] == 15500
    assert summary["total_investments"] == 21610
    assert summary["total_real_estate"] == 5000
    assert portfolio["total"] > 25000

    expected_prices = {
        "demo:fund:global:1": Decimal("51.4138984680"),
        "demo:fund:global:2": Decimal("58.8935012817"),
        "demo:fund:bond:1": Decimal("100.3751983643"),
        "demo:fund:bond:2": Decimal("99.9937973022"),
        "demo:fund:sp500:1": Decimal("14.0843000412"),
        "demo:fund:sp500:2": Decimal("14.6714000702"),
        "demo:fund:emerging:1": Decimal("240.4282989502"),
        "demo:fund:emerging:2": Decimal("315.8327026367"),
        "demo:stock:apple:1": Decimal("201.7460337064"),
        "demo:stock:apple:2": Decimal("259.9924197346"),
        "demo:stock:world:1": Decimal("109.2399978638"),
        "demo:stock:world:2": Decimal("119.5699996948"),
        "demo:stock:microsoft:1": Decimal("426.0272160230"),
        "demo:stock:microsoft:2": Decimal("354.7658479794"),
        "demo:stock:inditex:1": Decimal("53.4199981689"),
        "demo:stock:inditex:2": Decimal("53.4599990845"),
        "demo:crypto:btc:1": Decimal("76868.4140625000"),
        "demo:crypto:btc:2": Decimal("53440.2265625000"),
        "demo:crypto:eth:1": Decimal("2840.3762207031"),
        "demo:crypto:eth:2": Decimal("2056.5480957031"),
    }
    transactions = Transaction.objects.filter(account__workspace__slug="demo")
    assert {item.external_id: item.unit_price for item in transactions} == expected_prices
    for item in transactions:
        assert item.unit_price is not None
        calculated_amount = item.quantity * item.unit_price
        assert abs(calculated_amount - item.net_amount) < Decimal("0.00000001")

    expected_current_prices = {
        "IE00B03HCZ61": Decimal("61.4591000000"),
        "IE00B18GC888": Decimal("99.3291000000"),
        "IE00BYX5MX67": Decimal("16.1110000000"),
        "IE0031786142": Decimal("289.5780000000"),
        "US0378331005": Decimal("294.6311280000"),
        "IE00B4L5Y983": Decimal("123.4800000000"),
        "US5949181045": Decimal("391.2390300000"),
        "ES0148396007": Decimal("57.4800000000"),
        "BTC": Decimal("56201.9700000000"),
        "ETH": Decimal("1670.3500000000"),
    }
    assert {
        item.instrument.identifiers.get(is_primary=True).value: item.close
        for item in MarketPrice.objects.filter(
            instrument__workspace_links__workspace__slug="demo",
            source="demo",
        )
        .select_related("instrument")
        .prefetch_related("instrument__identifiers")
    } == expected_current_prices
