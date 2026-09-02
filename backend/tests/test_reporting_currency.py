from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from apps.api import views
from apps.market_data.fx import FxConversion
from apps.planning.models import BudgetLine
from apps.portfolio.models import ManualAsset
from apps.real_estate.models import RealEstateInvestment
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from django.core.cache import cache
from django.core.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.test import APIClient


def workspace_client(slug: str, base_currency: str) -> tuple[Workspace, APIClient]:
    workspace = Workspace.objects.create(name=slug.title(), slug=slug, base_currency=base_currency)
    user = User.objects.create_user(email=f"{slug}@example.com", password="password123")
    WorkspaceMembership.objects.create(workspace=workspace, user=user, role="owner")
    client = APIClient()
    client.force_authenticate(user)
    session = client.session
    session["active_workspace_id"] = str(workspace.pk)
    session.save()
    return workspace, client


@pytest.mark.django_db
def test_session_exposes_each_workspace_reporting_currency() -> None:
    workspace, client = workspace_client("usd-session", "USD")

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["workspaces"] == [
        {
            "id": str(workspace.pk),
            "name": "Usd-Session",
            "slug": "usd-session",
            "base_currency": "USD",
            "role": "owner",
        }
    ]


@pytest.mark.django_db
def test_reporting_currency_change_is_blocked_after_financial_data_exists() -> None:
    workspace = Workspace.objects.create(name="Reporting", slug="reporting", base_currency="USD")
    workspace.base_currency = "GBP"
    workspace.save()
    ManualAsset.objects.create(
        workspace=workspace,
        name="Cash reserve",
        asset_class="Cash",
        value=Decimal("100"),
        currency="GBP",
        valued_at=date(2026, 8, 1),
    )

    workspace.base_currency = "EUR"
    with pytest.raises(ValidationError) as exc_info:
        workspace.save()

    assert "base_currency" in exc_info.value.message_dict
    workspace.refresh_from_db()
    assert workspace.base_currency == "GBP"


@pytest.mark.django_db
def test_implicit_amounts_are_labeled_with_the_workspace_currency() -> None:
    workspace, client = workspace_client("usd-amounts", "USD")

    portfolio = client.post(
        "/api/portfolio",
        {"name": "Emergency fund", "asset_class": "Cash", "value": 500},
        format="json",
    )
    budget = client.put(
        "/api/budget",
        [{"categoria": "Housing", "cantidad": 1200, "tipo": "expense"}],
        format="json",
    )
    real_estate = client.post(
        "/api/real-estate",
        {
            "nombre": "Property note",
            "fecha_inicio": "2026-01-01",
            "capital_inicial": 1000,
            "capital_nuevo": 1000,
        },
        format="json",
    )

    assert portfolio.status_code == real_estate.status_code == 201
    assert budget.status_code == 200
    assert portfolio.json()["currency"] == "USD"
    assert budget.json()[0]["moneda"] == "USD"
    assert real_estate.json()["moneda"] == "USD"
    assert ManualAsset.objects.get(workspace=workspace).currency == "USD"
    assert BudgetLine.objects.get(workspace=workspace).currency == "USD"
    assert RealEstateInvestment.objects.get(workspace=workspace).currency == "USD"


@pytest.mark.django_db
def test_fund_history_cache_is_isolated_by_workspace_and_reporting_currency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache.clear()
    _eur_workspace, eur_client = workspace_client("eur-fund-cache", "EUR")
    _usd_workspace, usd_client = workspace_client("usd-fund-cache", "USD")
    rows = [
        {
            "isin": "TEST",
            "tipo_operacion": "SUSCRIPCION",
            "titulos": 1,
            "fecha_operacion": "2026-01-01",
            "importe_neto": 100,
            "importe_base": 100,
        }
    ]
    monkeypatch.setattr(views, "transaction_list", lambda *_args: Response(rows))
    monkeypatch.setattr(views, "workspace_instrument", lambda *_args: object())
    monkeypatch.setattr(views, "yahoo_ticker", lambda *_args: "TEST")
    monkeypatch.setattr(
        views,
        "yahoo_chart",
        lambda *_args, **_kwargs: (
            {"currency": "USD"},
            [{"fecha": "2026-01-02", "precio": 100}],
        ),
    )

    requested_bases: list[str] = []

    def rates(
        _quote: str, base: str, dates: list[date], **_kwargs: Any
    ) -> dict[date, FxConversion]:
        requested_bases.append(base)
        rate = Decimal("0.9") if base == "EUR" else Decimal("1")
        return {value: FxConversion(rate, value, "test") for value in dates}

    monkeypatch.setattr(views, "rates_to_base", rates)

    eur = eur_client.get("/api/investment-performance/fund?account_id=all&range=1y")
    usd = usd_client.get("/api/investment-performance/fund?account_id=all&range=1y")

    assert eur.status_code == usd.status_code == 200
    assert eur.json()["data"][0]["valor"] == 90
    assert usd.json()["data"][0]["valor"] == 100
    assert requested_bases == ["EUR", "USD"]
