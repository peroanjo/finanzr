from decimal import Decimal
from uuid import UUID

import pytest
from apps.common.models import InstallationSettings
from apps.users.models import User
from rest_framework.test import APIClient


@pytest.mark.django_db(transaction=True)
def test_real_estate_keeps_empty_expected_profit_for_client_fallback(
    real_estate_context: tuple[APIClient, User],
) -> None:
    client, _ = real_estate_context

    projects = client.get("/api/real-estate").json()
    malaga = next(item for item in projects if item["name"] == "Synthetic project")

    assert malaga["expected_profit"] is None


@pytest.mark.django_db(transaction=True)
def test_real_estate_uses_uuid_and_native_fields(
    real_estate_context: tuple[APIClient, User],
) -> None:
    client, _ = real_estate_context

    project = client.get("/api/real-estate").json()[0]

    UUID(project["id"])
    assert set(project) == {
        "id",
        "name",
        "platform",
        "status",
        "initial_capital",
        "new_capital",
        "returned_capital",
        "realized_profit",
        "net_realized_profit",
        "expected_profit",
        "net_expected_profit",
        "expected_irr_percent",
        "expected_term_months",
        "start_date",
        "maturity_date",
        "return_date",
        "movements",
        "origin",
        "tax_rate",
        "currency",
    }
    assert project["status"] == "active"
    delete_response = client.delete("/api/real-estate/1")
    assert delete_response.status_code == 404
    rejected = client.post(
        "/api/real-estate",
        {
            "nombre": "Legacy project",
            "fecha_inicio": "2026-01-01",
            "capital_inicial": 100,
        },
        format="json",
    )
    assert rejected.status_code == 400
    assert "non_field_errors" in rejected.json()["error"]


@pytest.mark.django_db(transaction=True)
def test_real_estate_preserves_multiple_dated_movements(
    real_estate_context: tuple[APIClient, User],
) -> None:
    client, _ = real_estate_context

    response = client.post(
        "/api/real-estate",
        {
            "name": "Proyecto con amortizaciones",
            "platform": "WeCity",
            "status": "completed",
            "initial_capital": 1500,
            "new_capital": 1500,
            "expected_profit": 100,
            "expected_irr_percent": 11,
            "expected_term_months": 18,
            "start_date": "2025-09-01",
            "maturity_date": "2027-03-01",
            "origin": "",
            "movements": [
                {
                    "flow_type": "capital_return",
                    "effective_date": "2026-06-22",
                    "amount": 970.96,
                    "note": "Primera amortización",
                },
                {
                    "flow_type": "capital_return",
                    "effective_date": "2026-07-14",
                    "amount": 529.04,
                    "note": "Amortización final",
                },
                {
                    "flow_type": "profit",
                    "effective_date": "2026-07-14",
                    "amount": 49.94,
                    "note": "Intereses",
                },
            ],
        },
        format="json",
    )

    assert response.status_code == 201
    project = response.json()
    assert project["returned_capital"] == 1500
    assert project["realized_profit"] == 49.94
    assert project["net_realized_profit"] == pytest.approx(40.4514)
    assert project["return_date"] == "2026-07-14"
    assert [movement["note"] for movement in project["movements"]] == [
        "Primera amortización",
        "Amortización final",
        "Intereses",
    ]
    assert project["movements"][-1]["applied_tax_rate"] == 19

    InstallationSettings.load().default_crowdfunding_tax_rate = Decimal("21.50")
    InstallationSettings.load().save(update_fields=("default_crowdfunding_tax_rate", "updated_at"))
    unchanged = next(
        item for item in client.get("/api/real-estate").json() if item["id"] == project["id"]
    )
    assert unchanged["net_realized_profit"] == pytest.approx(40.4514)

    updated = client.put(
        f"/api/real-estate/{project['id']}",
        {
            "name": "Proyecto con amortizaciones",
            "platform": "WeCity",
            "status": "completed",
            "initial_capital": 1500,
            "new_capital": 1500,
            "expected_profit": 100,
            "expected_irr_percent": 11,
            "expected_term_months": 18,
            "start_date": "2025-09-01",
            "maturity_date": "2027-03-01",
            "origin": "",
            "movements": [
                {
                    "id": movement["id"],
                    "flow_type": movement["flow_type"],
                    "effective_date": movement["effective_date"],
                    "amount": movement["amount"],
                    "note": movement["note"],
                }
                for movement in project["movements"]
            ],
        },
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["net_realized_profit"] == pytest.approx(40.4514)

    history = {row["fecha"]: row for row in client.get("/api/net-worth-history").json()}
    assert history["2026-06"]["inversiones"] - history["2026-06"]["balances"] >= 529.04
    assert history["2026-07"]["inversiones"] - history["2026-07"]["balances"] >= 0


@pytest.mark.django_db(transaction=True)
def test_real_estate_persists_and_updates_custom_tax_rate(
    real_estate_context: tuple[APIClient, User],
) -> None:
    client, _ = real_estate_context

    invalid_payload = {
        "name": "Proyecto inválido",
        "platform": "CrowdEstate",
        "status": "active",
        "initial_capital": 1000,
        "new_capital": 1000,
        "expected_profit": 120,
        "expected_irr_percent": 12,
        "expected_term_months": 12,
        "start_date": "2026-01-01",
        "maturity_date": "2027-01-01",
        "origin": "",
        "movements": [],
    }
    for value in (-1, 100.1, "invalid", "NaN"):
        response = client.post(
            "/api/real-estate",
            {**invalid_payload, "tax_rate": value},
            format="json",
        )
        assert response.status_code == 400
        assert "tax_rate" in response.json()["error"]

    created = client.post(
        "/api/real-estate",
        {
            "name": "Proyecto Extranjero",
            "platform": "CrowdEstate",
            "status": "active",
            "initial_capital": 1000,
            "new_capital": 1000,
            "expected_profit": 120,
            "expected_irr_percent": 12,
            "expected_term_months": 12,
            "start_date": "2026-01-01",
            "maturity_date": "2027-01-01",
            "tax_rate": 0,
            "origin": "",
            "movements": [],
        },
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["tax_rate"] == 0

    project_id = created.json()["id"]
    updated = client.put(
        f"/api/real-estate/{project_id}",
        {
            "name": "Proyecto Extranjero Modificado",
            "platform": "CrowdEstate",
            "status": "active",
            "initial_capital": 1000,
            "new_capital": 1000,
            "expected_profit": 120,
            "expected_irr_percent": 12,
            "expected_term_months": 12,
            "start_date": "2026-01-01",
            "maturity_date": "2027-01-01",
            "tax_rate": 15.5,
            "origin": "",
            "movements": [],
        },
        format="json",
    )
    assert updated.status_code == 200
    assert updated.json()["tax_rate"] == 15.5

    cleared = client.put(
        f"/api/real-estate/{project_id}",
        {
            "name": "Proyecto Extranjero Heredado",
            "platform": "CrowdEstate",
            "status": "active",
            "initial_capital": 1000,
            "new_capital": 1000,
            "expected_profit": 120,
            "expected_irr_percent": 12,
            "expected_term_months": 12,
            "start_date": "2026-01-01",
            "maturity_date": "2027-01-01",
            "tax_rate": None,
            "origin": "",
            "movements": [],
        },
        format="json",
    )
    assert cleared.status_code == 200
    assert cleared.json()["tax_rate"] is None
