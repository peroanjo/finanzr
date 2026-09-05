from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from apps.accounts.models import Account, FinancialProvider
from apps.portfolio.models import ManualAsset
from apps.users.models import User
from apps.workspaces.models import Workspace
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.mark.django_db(transaction=True)
def test_portfolio_native_contract_uses_uuid_and_english_fields(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    seeded_asset = ManualAsset.objects.get(name="Synthetic cash")
    assert (
        client.patch(
            "/api/auth/preferences", {"summary_sources": ["manual_assets"]}, format="json"
        ).status_code
        == 200
    )
    before = client.get("/api/summary").json()
    listed = client.get("/api/portfolio")

    assert listed.status_code == 200
    assert listed.json() == [
        {
            "id": str(seeded_asset.id),
            "name": "Synthetic cash",
            "asset_class": "Efectivo",
            "subtype": "Demo",
            "platform": "Manual",
            "value": 100,
            "currency": "EUR",
        }
    ]
    assert client.get("/api/portfolio/1").status_code == 404

    created = client.post(
        "/api/portfolio",
        {
            "name": "Native reserve",
            "asset_class": "Cash",
            "subtype": "Liquid",
            "platform": "Synthetic bank",
            "value": "1234.56789012",
        },
        format="json",
    )

    assert created.status_code == 201
    native = created.json()
    UUID(native["id"])
    assert native["name"] == "Native reserve"
    assert native["asset_class"] == "Cash"
    assert native["subtype"] == "Liquid"
    assert native["platform"] == "Synthetic bank"
    assert native["value"] == pytest.approx(1234.56789012)
    assert native["currency"] == "EUR"
    stored = ManualAsset.objects.get(pk=native["id"])
    assert stored.id == UUID(native["id"])
    after = client.get("/api/summary").json()
    assert after["net_worth"] == pytest.approx(before["net_worth"] + 1234.57)

    updated = client.put(
        f"/api/portfolio/{stored.id}",
        {"value": "1300.00000001"},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == str(stored.id)
    assert updated.json()["value"] == pytest.approx(1300.00000001)


@pytest.mark.django_db(transaction=True)
def test_portfolio_native_contract_resolves_and_clears_providers(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    provider = FinancialProvider.objects.create(
        slug="canonical-bank",
        name="Canonical Bank",
        provider_type=FinancialProvider.ProviderType.BANK,
    )
    created = client.post(
        "/api/portfolio",
        {
            "name": "Linked reserve",
            "asset_class": "Cash",
            "platform": "canonical bank",
            "value": 100,
        },
        format="json",
    )

    assert created.status_code == 201
    asset = ManualAsset.objects.get(pk=created.json()["id"])
    assert asset.provider_id == provider.id
    assert asset.provider_label == ""
    assert created.json()["platform"] == "Canonical Bank"

    renamed_asset = client.put(
        f"/api/portfolio/{asset.id}",
        {"name": "Renamed linked reserve"},
        format="json",
    )
    assert renamed_asset.status_code == 200
    asset.refresh_from_db()
    assert asset.provider_id == provider.id
    assert asset.provider_label == ""
    assert renamed_asset.json()["platform"] == "Canonical Bank"

    renamed = client.put(
        f"/api/portfolio/{asset.id}",
        {"platform": "Personal label"},
        format="json",
    )
    assert renamed.status_code == 200
    asset.refresh_from_db()
    assert asset.provider_id is None
    assert asset.provider_label == "Personal label"
    assert renamed.json()["platform"] == "Personal label"

    relinked = client.put(
        f"/api/portfolio/{asset.id}",
        {"platform": "CANONICAL BANK"},
        format="json",
    )
    assert relinked.status_code == 200
    asset.refresh_from_db()
    assert asset.provider_id == provider.id
    assert asset.provider_label == ""
    assert relinked.json()["platform"] == "Canonical Bank"

    cleared = client.put(
        f"/api/portfolio/{asset.id}",
        {"platform": ""},
        format="json",
    )
    assert cleared.status_code == 200
    asset.refresh_from_db()
    assert asset.provider_id is None
    assert asset.provider_label == ""
    assert cleared.json()["platform"] == ""
    exported = client.get("/api/account/export")
    assert exported.status_code == 200
    assert (
        next(row for row in exported.json()["portfolio"] if row["id"] == str(asset.id))["platform"]
        == ""
    )


@pytest.mark.django_db(transaction=True)
def test_portfolio_native_contract_rejects_legacy_fields_and_model_overflows(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    asset_id = client.get("/api/portfolio").json()[0]["id"]
    legacy_payload = {
        "nombre": "Rejected",
        "tipo_renta": "Cash",
        "efectivo": 100,
    }
    assert client.post("/api/portfolio", legacy_payload, format="json").status_code == 400
    assert (
        client.post(
            "/api/portfolio",
            {"name": "Valid", "asset_class": "Cash", "value": 100, "unknown": True},
            format="json",
        ).status_code
        == 400
    )

    for field, value in (
        ("name", "N" * 201),
        ("asset_class", "C" * 81),
        ("subtype", "S" * 121),
        ("platform", "P" * 161),
    ):
        assert (
            client.post(
                "/api/portfolio",
                {"name": "Valid", "asset_class": "Cash", "value": 100, field: value},
                format="json",
            ).status_code
            == 400
        )
        assert (
            client.put(f"/api/portfolio/{asset_id}", {field: value}, format="json").status_code
            == 400
        )


@pytest.mark.django_db(transaction=True)
def test_portfolio_native_contract_isolates_uuid_scope_and_types(
    api_context: tuple[APIClient, User],
) -> None:
    client, _ = api_context
    savings_id = Account.objects.get(kind=Account.Kind.SAVINGS).id
    foreign_workspace = Workspace.objects.create(
        name="Foreign portfolio workspace", slug="foreign-portfolio", base_currency="EUR"
    )
    foreign_asset = ManualAsset.objects.create(
        workspace=foreign_workspace,
        name="Foreign asset",
        asset_class="Cash",
        value=Decimal("50"),
        currency="EUR",
        valued_at=date(2028, 1, 31),
    )

    assert client.get("/api/portfolio/not-a-uuid").status_code == 404
    assert client.get("/api/portfolio/1").status_code == 404
    put_numeric_id = client.put("/api/portfolio/1", {}, format="json")
    assert put_numeric_id.status_code == 404
    deleted_numeric_id = client.delete("/api/portfolio/1")
    assert deleted_numeric_id.status_code == 404
    put_invalid_uuid = client.put("/api/portfolio/not-a-uuid", {}, format="json")
    assert put_invalid_uuid.status_code == 404
    put_savings_id = client.put(
        f"/api/portfolio/{savings_id}",
        {"name": "Wrong type"},
        format="json",
    )
    assert put_savings_id.status_code == 404
    put_foreign_asset = client.put(
        f"/api/portfolio/{foreign_asset.id}",
        {"name": "Should remain hidden"},
        format="json",
    )
    assert put_foreign_asset.status_code == 404
