"""Synthetic integration coverage for canonical records shared across workspaces."""

from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest
from apps.accounts.models import Account, AccountSnapshot
from apps.imports.models import ImportBatch
from apps.market_data.models import (
    Instrument,
    InstrumentIdentifier,
    StockSplit,
    WorkspaceMarketPriceOverride,
)
from apps.portfolio.models import ManualAsset
from apps.real_estate.models import RealEstateCashFlow, RealEstateInvestment
from apps.transactions.models import Transaction
from apps.users.models import User
from apps.workspaces.models import AssetShare, Workspace, WorkspaceMembership
from apps.workspaces.services import provision_personal_workspace
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def select(client: APIClient, workspace: Workspace) -> None:
    response = client.put(
        "/api/workspaces/current", {"workspace_id": str(workspace.pk)}, format="json"
    )
    assert response.status_code == 200


@pytest.fixture
def context() -> dict[str, Any]:
    a = User.objects.create_user(email="a@example.com", password="synthetic-password")
    b = User.objects.create_user(email="b@example.com", password="synthetic-password")
    private_a = provision_personal_workspace(a).workspace
    private_b = provision_personal_workspace(b).workspace
    common = Workspace.objects.create(name="Synthetic shared", slug="synthetic-shared")
    WorkspaceMembership.objects.create(user=a, workspace=common, role="owner")
    WorkspaceMembership.objects.create(user=b, workspace=common, role="editor")
    ca, cb = APIClient(), APIClient()
    ca.force_authenticate(a)
    cb.force_authenticate(b)
    select(ca, private_a)
    select(cb, common)
    account = Account.objects.create(workspace=private_a, name="Shared savings", kind="savings")
    hidden = Account.objects.create(workspace=private_a, name="Private savings", kind="savings")
    return dict(
        a=a,
        b=b,
        ca=ca,
        cb=cb,
        pa=private_a,
        pb=private_b,
        common=common,
        account=account,
        hidden=hidden,
    )


def grant(
    c: dict[str, Any], resource: Any = None, kind: str = "account", access: str = "read"
) -> dict[str, Any]:
    item = resource or c["account"]
    result = c["ca"].post(
        "/api/workspaces/shares",
        {
            "kind": kind,
            "resource_id": str(item.pk),
            "target_id": str(c["common"].pk),
            "access": access,
        },
        format="json",
    )
    assert result.status_code == 201, result.data
    return cast(dict[str, Any], result.json())


def test_share_exposes_exactly_one_record_and_its_history(context: dict[str, Any]) -> None:
    c = context
    AccountSnapshot.objects.create(
        account=c["account"], date="2026-01-31", value=100, base_value=100
    )
    AccountSnapshot.objects.create(
        account=c["hidden"], date="2026-01-31", value=9999, base_value=9999
    )
    grant(c)
    assert [row["id"] for row in c["cb"].get("/api/savings/accounts").json()] == [
        str(c["account"].pk)
    ]
    history = c["cb"].get("/api/savings/history").json()
    assert len(history) == 1 and history[0]["balance"] == 100
    assert c["cb"].get("/api/summary").json()["net_worth"] == 100
    assert c["ca"].get("/api/summary").json()["net_worth"] == 10099
    assert c["cb"].get(f"/api/savings/history?account_id={c['hidden'].pk}").status_code == 404
    assert "Private savings" not in c["cb"].get("/api/account/export").content.decode()
    assert (
        c["cb"]
        .put(f"/api/savings/accounts/{c['account'].pk}", {"name": "Denied"}, format="json")
        .status_code
        == 403
    )


def test_shared_edit_updates_canonical_record_and_never_duplicates(context: dict[str, Any]) -> None:
    c = context
    share = grant(c, access="edit")
    assert (
        c["cb"]
        .post(
            "/api/savings/history",
            {
                "account_id": str(c["account"].pk),
                "date": "2026-02-10",
                "balance": 250,
                "contribution": 250,
                "interest": 0,
            },
            format="json",
        )
        .status_code
        == 201
    )
    assert c["ca"].get("/api/savings/history").json()[0]["balance"] == 250
    assert AccountSnapshot.objects.filter(account=c["account"]).count() == 1
    assert Account.objects.count() == 2
    assert (
        c["cb"]
        .put(f"/api/savings/accounts/{c['account'].pk}", {"name": "One original"}, format="json")
        .status_code
        == 200
    )
    c["account"].refresh_from_db()
    assert c["account"].name == "One original"
    assert c["cb"].delete(f"/api/savings/accounts/{c['account'].pk}").status_code == 403
    assert c["cb"].delete(f"/api/workspaces/shares/{share['id']}").status_code == 403
    assert c["ca"].delete(f"/api/workspaces/shares/{share['id']}").status_code == 204
    assert c["cb"].get("/api/savings/accounts").json() == []
    assert AccountSnapshot.objects.filter(account=c["account"]).count() == 1


def test_effective_access_is_intersection_of_membership_and_grant(context: dict[str, Any]) -> None:
    c = context
    grant(c, access="edit")
    membership = c["b"].memberships.get(workspace=c["common"])
    membership.role = "viewer"
    membership.save()
    assert c["cb"].get("/api/savings/accounts").status_code == 200
    assert (
        c["cb"]
        .put(f"/api/savings/accounts/{c['account'].pk}", {"name": "Denied"}, format="json")
        .status_code
        == 403
    )
    select(c["cb"], c["pb"])
    assert c["cb"].get("/api/savings/accounts").json() == []
    assert (
        c["cb"]
        .put("/api/workspaces/current", {"workspace_id": str(c["pa"].pk)}, format="json")
        .status_code
        == 404
    )


def test_sharing_cannot_regrant_other_users_resources_or_target_private_space(
    context: dict[str, Any],
) -> None:
    c = context
    grant(c, access="edit")
    for actor, target in [(c["cb"], c["common"]), (c["ca"], c["pb"]), (c["ca"], c["pa"])]:
        result = actor.post(
            "/api/workspaces/shares",
            {
                "kind": "account",
                "resource_id": str(c["account"].pk),
                "target_id": str(target.pk),
                "access": "edit",
            },
            format="json",
        )
        assert result.status_code == 404
    assert len(c["cb"].get("/api/workspaces/shares").json()["incoming"]) == 1
    assert c["cb"].get("/api/workspaces/shares").json()["outgoing"] == []


def test_grants_are_idempotent_and_freeze_reporting_currencies(context: dict[str, Any]) -> None:
    c = context
    first = grant(c)
    second = grant(c, access="edit")
    assert first["id"] == second["id"]
    assert AssetShare.objects.count() == 1
    for item in [c["pa"], c["common"]]:
        item.base_currency = "USD"
        with pytest.raises(ValidationError):
            item.save()
    other = Workspace.objects.create(
        name="Synthetic USD", slug="synthetic-usd", base_currency="USD"
    )
    WorkspaceMembership.objects.create(workspace=other, user=c["a"], role="owner")
    result = c["ca"].post(
        "/api/workspaces/shares",
        {
            "kind": "account",
            "resource_id": str(c["account"].pk),
            "target_id": str(other.pk),
            "access": "read",
        },
        format="json",
    )
    assert result.status_code == 400


def test_manual_and_real_estate_shares_edit_original_values(context: dict[str, Any]) -> None:
    c = context
    asset = ManualAsset.objects.create(
        workspace=c["pa"],
        name="Synthetic asset",
        asset_class="Other",
        value=200,
        currency="EUR",
        valued_at=date(2026, 1, 1),
    )
    property = RealEstateInvestment.objects.create(
        workspace=c["pa"], name="Synthetic property", start_date="2026-01-01"
    )
    RealEstateCashFlow.objects.create(investment=property, flow_type="contribution", amount=100)
    grant(c, asset, "manual_asset", "edit")
    grant(c, property, "real_estate", "read")
    assert c["cb"].get("/api/portfolio").json()[0]["id"] == str(asset.pk)
    assert (
        c["cb"].put(f"/api/portfolio/{asset.pk}", {"value": 350}, format="json").status_code == 200
    )
    asset.refresh_from_db()
    assert asset.value == 350
    assert c["cb"].delete(f"/api/portfolio/{asset.pk}").status_code == 403
    assert c["cb"].get("/api/real-estate").json()[0]["id"] == str(property.pk)
    assert (
        c["cb"]
        .put(f"/api/real-estate/{property.pk}", {"name": "Denied"}, format="json")
        .status_code
        == 403
    )


def test_create_invite_accept_preserves_both_private_workspaces(context: dict[str, Any]) -> None:
    c = context
    assert (
        c["ca"]
        .post(
            "/api/workspaces/invitations", {"email": c["b"].email, "role": "editor"}, format="json"
        )
        .status_code
        == 403
    )
    created = c["ca"].post("/api/workspaces", {"name": "Another synthetic space"}, format="json")
    assert created.status_code == 201
    common_id = created.json()["active_workspace_id"]
    invitation = c["ca"].post(
        "/api/workspaces/invitations", {"email": c["b"].email, "role": "editor"}, format="json"
    )
    assert invitation.status_code == 201
    code = invitation.json()["token"]
    assert (
        c["ca"]
        .post("/api/workspaces/invitations/accept", {"token": code}, format="json")
        .status_code
        == 400
    )
    accepted = c["cb"].post("/api/workspaces/invitations/accept", {"token": code}, format="json")
    assert accepted.status_code == 200
    assert accepted.json()["active_workspace_id"] == common_id
    assert {row["id"] for row in accepted.json()["workspaces"]} == {
        str(c["pb"].pk),
        str(c["common"].pk),
        common_id,
    }
    assert (
        c["cb"]
        .post("/api/workspaces/invitations/accept", {"token": code}, format="json")
        .status_code
        == 400
    )
    assert Workspace.objects.get(pk=common_id).accounts.count() == 0


def test_member_management_retains_last_owner_and_revokes_access(context: dict[str, Any]) -> None:
    c = context
    select(c["ca"], c["common"])
    ma = c["a"].memberships.get(workspace=c["common"])
    mb = c["b"].memberships.get(workspace=c["common"])
    assert c["ca"].delete(f"/api/workspaces/members/{ma.pk}").status_code == 409
    assert (
        c["cb"]
        .patch(f"/api/workspaces/members/{ma.pk}", {"role": "viewer"}, format="json")
        .status_code
        == 403
    )
    assert (
        c["ca"]
        .patch(f"/api/workspaces/members/{mb.pk}", {"role": "owner"}, format="json")
        .status_code
        == 200
    )
    assert c["ca"].delete(f"/api/workspaces/members/{ma.pk}").status_code == 200
    assert (
        c["ca"]
        .put("/api/workspaces/current", {"workspace_id": str(c["common"].pk)}, format="json")
        .status_code
        == 404
    )
    assert c["b"].memberships.filter(workspace=c["common"], role="owner").exists()


def test_stale_workspace_context_rejects_financial_writes(context: dict[str, Any]) -> None:
    c = context
    select(c["ca"], c["common"])
    response = c["ca"].post(
        "/api/savings/accounts",
        {"name": "Must not exist"},
        format="json",
        HTTP_X_WORKSPACE_ID=str(c["pa"].pk),
    )
    assert response.status_code == 409
    assert not Account.objects.filter(name="Must not exist").exists()


def stock(c: dict[str, Any], owner: Workspace, name: str) -> tuple[Account, Instrument]:
    account = Account.objects.create(workspace=owner, name=name, kind="stocks")
    instrument, _ = Instrument.objects.get_or_create(kind="stock", name="Synthetic stock")
    InstrumentIdentifier.objects.get_or_create(
        instrument=instrument, scheme="isin", value="US0000000001", venue=""
    )
    Transaction.objects.create(
        account=account,
        instrument=instrument,
        trade_date="2026-01-01",
        operation_type="buy",
        cash_flow_type="contribution",
        quantity=10,
        unit_price=10,
        net_amount=100,
        currency="EUR",
        base_currency="EUR",
        base_unit_price=10,
        base_net_amount=100,
    )
    return account, instrument


def test_traded_shares_preserve_positions_quotes_splits_and_private_isolation(
    context: dict[str, Any],
) -> None:
    c = context
    account, instrument = stock(c, c["pa"], "Shared stocks")
    hidden, _ = stock(c, c["pa"], "Hidden stocks")
    grant(c, account, access="edit")
    WorkspaceMarketPriceOverride.objects.create(
        workspace=c["pa"], instrument=instrument, close=15, currency="EUR", quoted_at=timezone.now()
    )
    split = StockSplit.objects.create(
        workspace=c["pa"], instrument=instrument, effective_date="2026-02-01", ratio=2
    )
    orders = c["cb"].get("/api/stock-orders").json()
    assert len(orders) == 1 and orders[0]["account_id"] == str(account.pk)
    assert c["cb"].get("/api/stock-prices").json()[0]["close"] == 15
    assert (
        c["cb"].get("/api/stock-analysis").json()
        == c["ca"].get(f"/api/stock-analysis?account_id={account.pk}").json()
    )
    assert c["cb"].get("/api/stock-splits").json()[0]["id"] == str(split.pk)
    assert c["cb"].delete(f"/api/stock-splits/{split.pk}").status_code == 403
    assert (
        c["cb"].put(f"/api/stock-prices/{instrument.pk}", {"close": 99}, format="json").status_code
        == 403
    )
    hidden_order = hidden.transactions.get()
    assert c["cb"].delete(f"/api/stock-orders/{hidden_order.pk}").status_code == 404
    assert c["cb"].delete(f"/api/stock-orders/{orders[0]['id']}").status_code == 200
    assert Transaction.objects.filter(account=hidden).count() == 1


def test_same_instrument_from_two_owners_is_counted_once_per_account(
    context: dict[str, Any],
) -> None:
    c = context
    a, instrument = stock(c, c["pa"], "A stocks")
    b, _ = stock(c, c["pb"], "B stocks")
    grant(c, a)
    AssetShare.objects.create(target=c["common"], account=b, access="read")
    response = c["cb"].get("/api/stock-analysis")
    assert response.status_code == 200
    assert response.json()[0]["quantity"] == 20
    WorkspaceMarketPriceOverride.objects.create(
        workspace=c["pa"], instrument=instrument, close=15, currency="EUR", quoted_at=timezone.now()
    )
    assert c["cb"].get("/api/stock-analysis").status_code == 400


def test_archiving_shared_space_preserves_original_and_prevents_selection(
    context: dict[str, Any],
) -> None:
    c = context
    grant(c)
    select(c["ca"], c["common"])
    assert c["ca"].delete("/api/workspaces/settings").status_code == 200
    assert (
        c["cb"]
        .put("/api/workspaces/current", {"workspace_id": str(c["common"].pk)}, format="json")
        .status_code
        == 404
    )
    assert Account.objects.filter(pk=c["account"].pk).exists()
    assert c["cb"].get("/api/savings/accounts").json() == []


def test_import_from_shared_account_is_deduplicated_in_the_original_workspace(
    context: dict[str, Any],
) -> None:
    from django.core.files.uploadedfile import SimpleUploadedFile

    c = context
    account = Account.objects.create(
        workspace=c["pa"], name="Synthetic crypto", kind="crypto", importer_slug="kraken_spot"
    )
    grant(c, account, access="edit")
    content = (
        b"txid,pair,time,type,price,cost,fee,vol\n"
        b"shared-tx,BTC/EUR,2026-07-20 12:00:00,buy,100000,100,1,0.001\n"
    )
    first = c["cb"].post(
        f"/api/account-imports/crypto/{account.pk}",
        {"file": SimpleUploadedFile("synthetic.csv", content)},
    )
    assert first.status_code == 200 and first.json()["imported"] == 1
    batch = ImportBatch.objects.get(account=account)
    assert batch.workspace_id == c["pa"].pk
    again = c["ca"].post(
        f"/api/account-imports/crypto/{account.pk}",
        {"file": SimpleUploadedFile("synthetic.csv", content)},
    )
    assert again.status_code == 200 and again.json()["duplicate"] is True
    assert ImportBatch.objects.filter(account=account).count() == 1
    assert Transaction.objects.filter(account=account).count() == 1
    grant(c, account, access="read")
    denied = c["cb"].post(
        f"/api/account-imports/crypto/{account.pk}",
        {"file": SimpleUploadedFile("synthetic.csv", content)},
    )
    assert denied.status_code == 403


def test_shared_quotes_history_and_charts_keep_each_owners_fx_context(
    context: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.api import market_views
    from apps.market_data.models import MarketPrice, WorkspaceFxOverride

    c = context
    instruments = []
    for index, (owner, rate) in enumerate([(c["pa"], Decimal("0.5")), (c["pb"], Decimal("0.75"))]):
        account = Account.objects.create(
            workspace=owner, name=f"Synthetic account {index}", kind="stocks"
        )
        instrument = Instrument.objects.create(
            kind="stock", name=f"Synthetic stock {index}", quote_currency="USD"
        )
        InstrumentIdentifier.objects.create(
            instrument=instrument, scheme="isin", value=f"US000000000{index}", venue=""
        )
        Transaction.objects.create(
            account=account,
            instrument=instrument,
            trade_date="2026-01-01",
            operation_type="buy",
            cash_flow_type="contribution",
            quantity=1,
            unit_price=100,
            net_amount=100,
            currency="USD",
            base_currency="EUR",
            base_unit_price=100 * rate,
            base_net_amount=100 * rate,
        )
        WorkspaceFxOverride.objects.create(
            workspace=owner,
            quote_currency="USD",
            base_currency="EUR",
            rate_date="2026-01-31",
            rate=rate,
        )
        MarketPrice.objects.create(
            instrument=instrument,
            quoted_at=timezone.now().replace(year=2026, month=1, day=31),
            close=200,
            granularity="spot",
            currency="USD",
            source="synthetic",
        )
        AssetShare.objects.create(target=c["common"], account=account)
        instruments.append(instrument)
    assert (
        c["cb"]
        .patch("/api/auth/preferences", {"summary_sources": ["stocks"]}, format="json")
        .status_code
        == 200
    )
    summary = c["cb"].get("/api/summary")
    assert summary.status_code == 200
    assert summary.json()["net_worth"] == 250
    prices = c["cb"].get("/api/stock-prices").json()
    assert sorted(row["base_close"] for row in prices) == [100, 150]
    monkeypatch.setattr(market_views, "yahoo_ticker", lambda instrument: "SYNTH")
    monkeypatch.setattr(
        market_views,
        "yahoo_chart",
        lambda *args, **kwargs: (
            {"currency": "USD"},
            [{"fecha": "2026-01-31", "open": 200, "high": 200, "low": 200, "close": 200}],
        ),
    )
    assert c["cb"].get(f"/api/stock-chart/{instruments[0].pk}").json()["data"][0]["close"] == 100
    assert c["cb"].get(f"/api/stock-chart/{instruments[1].pk}").json()["data"][0]["close"] == 150


def test_own_and_shared_positions_reject_conflicting_market_settings(
    context: dict[str, Any],
) -> None:
    c = context
    source, instrument = stock(c, c["pa"], "Shared")
    stock(c, c["common"], "Native")
    grant(c, source)
    WorkspaceMarketPriceOverride.objects.create(
        workspace=c["pa"], instrument=instrument, close=15, currency="EUR", quoted_at=timezone.now()
    )
    assert c["cb"].get("/api/stock-analysis").status_code == 400


def test_removed_member_cannot_access_shared_asset(
    context: dict[str, Any],
) -> None:
    c = context
    grant(c, access="edit")
    select(c["ca"], c["common"])
    member = c["b"].memberships.get(workspace=c["common"])
    assert c["ca"].delete(f"/api/workspaces/members/{member.pk}").status_code == 200
    assert c["cb"].get("/api/savings/accounts").json() == []
    assert (
        c["cb"]
        .put(f"/api/savings/accounts/{c['account'].pk}", {"name": "Denied"}, format="json")
        .status_code
        == 404
    )
