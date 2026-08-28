from datetime import date
from decimal import Decimal

import pytest
from apps.api import fx_views
from apps.market_data import fx
from apps.market_data.models import FxRate, WorkspaceFxOverride
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from rest_framework.test import APIClient


@pytest.fixture
def auth_client() -> APIClient:
    workspace = Workspace.objects.create(name="Test Space", slug="test-space", base_currency="EUR")
    user = User.objects.create_user(email="user@example.com", password="password123")
    WorkspaceMembership.objects.create(workspace=workspace, user=user, role="owner")
    client = APIClient()
    client.force_authenticate(user=user)
    session = client.session
    session["active_workspace_id"] = str(workspace.id)
    session.save()
    return client


@pytest.mark.django_db
def test_fx_rates_list_and_create(auth_client: APIClient) -> None:
    FxRate.objects.create(
        quote_currency="USD",
        base_currency="EUR",
        rate_date=date(2026, 1, 15),
        rate=Decimal("0.92"),
        source="yahoo",
    )

    # Test GET list
    resp = auth_client.get("/api/fx-rates")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["quote_currency"] == "USD"
    assert items[0]["base_currency"] == "EUR"
    assert items[0]["rate"] == 0.92
    assert items[0]["scope"] == "provider"

    # Test POST create
    create_resp = auth_client.post(
        "/api/fx-rates",
        {
            "quote_currency": "GBP",
            "base_currency": "EUR",
            "rate_date": "2026-02-01",
            "rate": "1.18",
            "source": "manual",
        },
        format="json",
    )
    assert create_resp.status_code in (200, 201)
    data = create_resp.json()
    assert data["quote_currency"] == "GBP"
    assert data["rate"] == 1.18
    assert data["scope"] == "workspace"
    assert FxRate.objects.count() == 1
    assert WorkspaceFxOverride.objects.count() == 1


@pytest.mark.django_db
def test_fx_rate_update_and_delete(auth_client: APIClient) -> None:
    rate_obj = FxRate.objects.create(
        quote_currency="USD",
        base_currency="EUR",
        rate_date=date(2026, 1, 15),
        rate=Decimal("0.90"),
        source="yahoo",
    )

    # PUT update
    update_resp = auth_client.put(
        f"/api/fx-rates/{rate_obj.pk}",
        {"rate": "0.95"},
        format="json",
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["rate"] == 0.95
    rate_obj.refresh_from_db()
    assert rate_obj.rate == Decimal("0.90")
    override = WorkspaceFxOverride.objects.get()
    assert override.rate == Decimal("0.95")

    # DELETE only removes the workspace override.
    delete_resp = auth_client.delete(f"/api/fx-rates/{override.pk}")
    assert delete_resp.status_code == 200
    assert WorkspaceFxOverride.objects.count() == 0
    assert FxRate.objects.count() == 1


@pytest.mark.django_db
def test_fx_rate_delete_pair_removes_the_complete_history(auth_client: APIClient) -> None:
    workspace = Workspace.objects.get(slug="test-space")
    first_rate = WorkspaceFxOverride.objects.create(
        workspace=workspace,
        quote_currency="USD",
        base_currency="EUR",
        rate_date=date(2026, 1, 14),
        rate=Decimal("0.91"),
        source="manual",
    )
    WorkspaceFxOverride.objects.create(
        workspace=workspace,
        quote_currency="USD",
        base_currency="EUR",
        rate_date=date(2026, 1, 15),
        rate=Decimal("0.92"),
        source="manual",
    )
    WorkspaceFxOverride.objects.create(
        workspace=workspace,
        quote_currency="GBP",
        base_currency="EUR",
        rate_date=date(2026, 1, 15),
        rate=Decimal("1.18"),
        source="manual",
    )

    response = auth_client.delete(f"/api/fx-rates/{first_rate.pk}?scope=pair")

    assert response.status_code == 200
    assert response.json()["deleted_count"] == 2
    assert list(WorkspaceFxOverride.objects.values_list("quote_currency", flat=True)) == ["GBP"]


@pytest.mark.django_db
def test_live_conversion_does_not_recreate_a_deleted_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    requested_date = date(2026, 1, 15)
    monkeypatch.setattr(
        fx,
        "_fetch_pair_rate",
        lambda *_args: fx.FxConversion(Decimal("0.92"), requested_date, "yahoo"),
    )

    conversion = fx.rate_to_base("USD", "EUR", requested_date, persist=False)

    assert conversion.rate == Decimal("0.92")
    assert FxRate.objects.count() == 0


@pytest.mark.django_db
def test_fetch_fx_rates_only_updates_saved_pairs(
    auth_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FxRate.objects.create(
        quote_currency="GBP",
        base_currency="EUR",
        rate_date=date(2026, 1, 15),
        rate=Decimal("1.18"),
        source="yahoo",
    )
    requested_pairs: list[tuple[str, str]] = []

    def fetch_saved_pair(
        quote: str,
        base: str,
        *_args: object,
        **_kwargs: object,
    ) -> fx.FxConversion:
        requested_pairs.append((quote, base))
        return fx.FxConversion(Decimal("1.18"), date(2026, 1, 15), "yahoo")

    monkeypatch.setattr(fx_views, "rate_to_base", fetch_saved_pair)

    response = auth_client.post("/api/fx-rates/fetch")

    assert response.status_code == 200
    assert response.json()["updated_count"] == 1
    assert requested_pairs == [("GBP", "EUR")]


@pytest.mark.django_db
def test_fx_convert_endpoint(auth_client: APIClient) -> None:
    FxRate.objects.create(
        quote_currency="USD",
        base_currency="EUR",
        rate_date=date(2026, 1, 10),
        rate=Decimal("0.92"),
        source="test",
    )

    resp = auth_client.get("/api/fx-rates/convert?amount=100&from=USD&to=EUR&date=2026-01-10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["from_currency"] == "USD"
    assert data["to_currency"] == "EUR"
    assert data["original_amount"] == 100
    assert data["converted_amount"] == 92.0
    assert data["rate"] == 0.92


@pytest.mark.django_db
def test_fx_chart_uses_direct_yahoo_history_without_persisting(
    auth_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    def direct_history(
        ticker: str, **kwargs: object
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        requests.append((ticker, kwargs))
        return {}, [
            {"fecha": "2026-01-02", "precio": 0.92},
            {"fecha": "2026-01-03", "precio": 0.93},
        ]

    monkeypatch.setattr(fx, "yahoo_chart", direct_history)

    response = auth_client.get("/api/fx-rates/chart?from=USD&to=EUR&range=invalid")

    assert response.status_code == 200
    assert response.json() == {
        "from_currency": "USD",
        "to_currency": "EUR",
        "range": "1y",
        "data": [
            {"fecha": "2026-01-02", "rate": 0.92},
            {"fecha": "2026-01-03", "rate": 0.93},
        ],
    }
    assert requests == [("USDEUR=X", {"range_name": "1y", "interval": "1d"})]
    assert FxRate.objects.count() == 0


@pytest.mark.django_db
def test_fx_chart_uses_custom_dates_without_persisting(
    auth_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    def custom_history(
        ticker: str, **kwargs: object
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        requests.append((ticker, kwargs))
        return {}, [{"fecha": "2025-02-14", "precio": 0.95}]

    monkeypatch.setattr(fx, "yahoo_chart", custom_history)

    response = auth_client.get(
        "/api/fx-rates/chart?from=USD&to=EUR&start=2024-01-01&end=2025-02-14"
    )

    assert response.status_code == 200
    assert response.json()["range"] == "custom"
    assert requests == [
        (
            "USDEUR=X",
            {"interval": "1wk", "start": "2024-01-01", "end": "2025-02-14"},
        )
    ]
    assert FxRate.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    [
        "start=2025-01-01",
        "start=invalid&end=2025-01-01",
        "start=2025-02-01&end=2025-01-01",
    ],
)
def test_fx_chart_rejects_invalid_custom_dates(auth_client: APIClient, query: str) -> None:
    response = auth_client.get(f"/api/fx-rates/chart?from=USD&to=EUR&{query}")

    assert response.status_code == 400


@pytest.mark.django_db
def test_fx_chart_falls_back_to_inverse_yahoo_history(
    auth_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tickers: list[str] = []

    def inverse_history(
        ticker: str, **_kwargs: object
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        tickers.append(ticker)
        if ticker == "USDEUR=X":
            raise fx.MarketDataError("Direct pair unavailable")
        return {}, [{"fecha": "2026-01-02", "precio": 1.25}]

    monkeypatch.setattr(fx, "yahoo_chart", inverse_history)

    response = auth_client.get("/api/fx-rates/chart?from=USD&to=EUR&range=2y")

    assert response.status_code == 200
    assert response.json()["data"] == [{"fecha": "2026-01-02", "rate": 0.8}]
    assert tickers == ["USDEUR=X", "EURUSD=X"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("quote", "base", "provider_rate", "expected_rate", "ticker"),
    [
        ("USD", "GBp", 0.8, 80.0, "USDGBP=X"),
        ("GBp", "USD", 1.25, 0.0125, "GBPUSD=X"),
    ],
)
def test_fx_chart_converts_gbp_and_gbp_quote_units(
    auth_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
    quote: str,
    base: str,
    provider_rate: float,
    expected_rate: float,
    ticker: str,
) -> None:
    requested_tickers: list[str] = []

    def history(
        symbol: str, **_kwargs: object
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        requested_tickers.append(symbol)
        return {}, [{"fecha": "2026-01-02", "precio": provider_rate}]

    monkeypatch.setattr(
        fx,
        "yahoo_chart",
        history,
    )

    response = auth_client.get(f"/api/fx-rates/chart?from={quote}&to={base}")

    assert response.status_code == 200
    assert response.json()["data"] == [{"fecha": "2026-01-02", "rate": expected_rate}]
    assert requested_tickers == [ticker]
    assert FxRate.objects.count() == 0


@pytest.mark.django_db
def test_fx_chart_returns_provider_failure_as_bad_gateway(
    auth_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        fx,
        "yahoo_chart",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(fx.MarketDataError("Unavailable")),
    )

    response = auth_client.get("/api/fx-rates/chart?from=USD&to=EUR")

    assert response.status_code == 502
    assert "error" in response.json()


@pytest.mark.django_db
def test_fx_chart_provider_failure_is_localized_in_spanish(
    auth_client: APIClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        fx,
        "yahoo_chart",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(fx.MarketDataError("Unavailable")),
    )

    response = auth_client.get(
        "/api/fx-rates/chart?from=USD&to=EUR",
        HTTP_ACCEPT_LANGUAGE="es",
    )

    assert response.status_code == 502
    assert response.json()["error"].startswith("No hay histórico de tipos de cambio disponible")


@pytest.mark.django_db
def test_workspace_overrides_are_isolated(auth_client: APIClient) -> None:
    second_workspace = Workspace.objects.create(
        name="Second Space", slug="second-space", base_currency="EUR"
    )
    second_user = User.objects.create_user(email="second@example.com", password="password123")
    WorkspaceMembership.objects.create(workspace=second_workspace, user=second_user, role="owner")
    second_client = APIClient()
    second_client.force_authenticate(user=second_user)
    second_session = second_client.session
    second_session["active_workspace_id"] = str(second_workspace.id)
    second_session.save()

    created = auth_client.post(
        "/api/fx-rates",
        {
            "quote_currency": "USD",
            "base_currency": "EUR",
            "rate_date": "2026-01-15",
            "rate": "0.95",
        },
        format="json",
    )

    assert created.status_code == 201
    assert len(auth_client.get("/api/fx-rates").json()) == 1
    assert second_client.get("/api/fx-rates").json() == []


@pytest.mark.django_db
def test_workspace_override_precedes_deterministic_provider_rate(
    auth_client: APIClient,
) -> None:
    workspace = Workspace.objects.get(slug="test-space")
    requested_date = date(2026, 1, 15)
    FxRate.objects.create(
        quote_currency="USD",
        base_currency="EUR",
        rate_date=requested_date,
        rate=Decimal("0.80"),
        source="secondary",
    )
    FxRate.objects.create(
        quote_currency="USD",
        base_currency="EUR",
        rate_date=requested_date,
        rate=Decimal("0.90"),
        source="yahoo",
    )
    override = WorkspaceFxOverride.objects.create(
        workspace=workspace,
        quote_currency="USD",
        base_currency="EUR",
        rate_date=requested_date,
        rate=Decimal("0.95"),
    )

    selected = fx.rate_to_base("USD", "EUR", requested_date, workspace=workspace)
    assert selected.rate == Decimal("0.95")
    assert selected.source == "manual"

    override.delete()
    provider = fx.rate_to_base("USD", "EUR", requested_date, workspace=workspace)
    assert provider.rate == Decimal("0.90")
    assert provider.source == "yahoo"


@pytest.mark.django_db
def test_stored_inverse_workspace_override_is_reused(auth_client: APIClient) -> None:
    workspace = Workspace.objects.get(slug="test-space")
    requested_date = date(2026, 1, 15)
    WorkspaceFxOverride.objects.create(
        workspace=workspace,
        quote_currency="EUR",
        base_currency="USD",
        rate_date=requested_date,
        rate=Decimal("1.25"),
    )

    conversion = fx.rate_to_base("USD", "EUR", requested_date, workspace=workspace)

    assert conversion.rate == Decimal("0.8")
    assert conversion.source == "manual"


@pytest.mark.django_db
def test_stored_inverse_provider_rate_is_reused_without_fetching(
    auth_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = Workspace.objects.get(slug="test-space")
    requested_date = date(2026, 1, 15)
    FxRate.objects.create(
        quote_currency="EUR",
        base_currency="USD",
        rate_date=requested_date,
        rate=Decimal("1.25"),
        source="yahoo",
    )
    monkeypatch.setattr(
        fx,
        "_fetch_pair_rate",
        lambda *_args: pytest.fail("The stored inverse rate should be reused"),
    )

    conversion = fx.rate_to_base("USD", "EUR", requested_date, workspace=workspace)

    assert conversion.rate == Decimal("0.8")
    assert conversion.source == "yahoo"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("quote", "base", "provider_rate", "expected"),
    [
        ("USD", "GBp", "0.8", Decimal("80.0")),
        ("GBp", "USD", "1.25", Decimal("0.0125")),
    ],
)
def test_point_conversion_scales_gbp_quote_units_in_both_directions(
    monkeypatch: pytest.MonkeyPatch,
    quote: str,
    base: str,
    provider_rate: str,
    expected: Decimal,
) -> None:
    monkeypatch.setattr(
        fx,
        "yahoo_chart",
        lambda *_args, **_kwargs: (
            {},
            [{"fecha": "2026-01-15", "precio": provider_rate}],
        ),
    )

    conversion = fx.rate_to_base(quote, base, date(2026, 1, 15), persist=False)
    assert conversion.rate == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        {"quote_currency": "US", "base_currency": "EUR", "rate": "1"},
        {"quote_currency": "EUR", "base_currency": "EUR", "rate": "1"},
    ],
)
def test_fx_rate_api_rejects_invalid_pairs(auth_client: APIClient, payload: dict[str, str]) -> None:
    response = auth_client.post(
        "/api/fx-rates",
        {**payload, "rate_date": "2026-01-15"},
        format="json",
    )
    assert response.status_code == 400
