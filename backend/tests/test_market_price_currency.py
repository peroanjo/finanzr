from datetime import UTC, date, datetime
from decimal import Decimal
from typing import NoReturn

import pytest
from apps.api import views
from apps.market_data.fx import CurrencyConversionError, FxConversion
from apps.market_data.models import (
    FxRate,
    Instrument,
    InstrumentIdentifier,
    MarketPrice,
    WorkspaceInstrument,
    WorkspaceMarketPriceOverride,
)
from apps.users.models import User
from apps.workspaces.models import Workspace, WorkspaceMembership
from rest_framework.test import APIClient


def workspace_client(slug: str, base_currency: str) -> tuple[Workspace, APIClient]:
    workspace = Workspace.objects.create(name=slug.title(), slug=slug, base_currency=base_currency)
    user = User.objects.create_user(email=f"{slug}@example.com", password="password123")
    WorkspaceMembership.objects.create(workspace=workspace, user=user, role="owner")
    client = APIClient()
    client.force_authenticate(user=user)
    session = client.session
    session["active_workspace_id"] = str(workspace.id)
    session.save()
    return workspace, client


def shared_instrument(
    first: Workspace, second: Workspace | None = None, *, kind: str = Instrument.Kind.STOCK
) -> Instrument:
    instrument = Instrument.objects.create(
        kind=kind,
        name="Shared asset",
        quote_currency="USD",
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value="TEST00000001",
        is_primary=True,
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.YAHOO,
        value="TEST",
        is_primary=True,
    )
    WorkspaceInstrument.objects.create(workspace=first, instrument=instrument)
    if second is not None:
        WorkspaceInstrument.objects.create(workspace=second, instrument=instrument)
    return instrument


@pytest.mark.django_db
def test_native_market_price_is_converted_per_workspace() -> None:
    eur_workspace, eur_client = workspace_client("eur-space", "EUR")
    usd_workspace, usd_client = workspace_client("usd-space", "USD")
    instrument = shared_instrument(eur_workspace, usd_workspace)
    quote_date = date(2026, 1, 15)
    price = MarketPrice.objects.create(
        instrument=instrument,
        quoted_at=datetime(2026, 1, 15, 12, tzinfo=UTC),
        granularity=MarketPrice.Granularity.SPOT,
        close=Decimal("100"),
        currency="USD",
        source="yahoo",
    )
    FxRate.objects.create(
        quote_currency="USD",
        base_currency="EUR",
        rate_date=quote_date,
        rate=Decimal("0.9"),
        source="yahoo",
    )

    eur_row = eur_client.get("/api/stock-prices").json()[0]
    usd_row = usd_client.get("/api/stock-prices").json()[0]

    assert eur_row["precio"] == 90.0
    assert eur_row["moneda"] == "USD"
    assert eur_row["moneda_base"] == "EUR"
    assert usd_row["precio"] == 100.0
    assert usd_row["moneda_base"] == "USD"
    price.refresh_from_db()
    assert price.close == Decimal("100")
    assert price.currency == "USD"


@pytest.mark.django_db
def test_manual_native_price_is_private_to_its_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eur_workspace, eur_client = workspace_client("manual-eur", "EUR")
    usd_workspace, usd_client = workspace_client("manual-usd", "USD")
    instrument = shared_instrument(eur_workspace, usd_workspace, kind=Instrument.Kind.FUND)
    MarketPrice.objects.create(
        instrument=instrument,
        quoted_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
        granularity=MarketPrice.Granularity.SPOT,
        close=Decimal("100"),
        currency="USD",
        source="yahoo",
    )
    monkeypatch.setattr(
        views,
        "rate_to_base",
        lambda _quote, base, requested_date, **_kwargs: FxConversion(
            Decimal("0.9") if base == "EUR" else Decimal("1"),
            requested_date,
            "test",
        ),
    )

    response = eur_client.put(
        "/api/fund-prices/TEST00000001",
        {"precio": "110", "moneda": "USD"},
        format="json",
    )

    assert response.status_code == 200
    assert MarketPrice.objects.filter(source="manual").count() == 0
    override = WorkspaceMarketPriceOverride.objects.get()
    assert override.workspace == eur_workspace
    assert override.close == Decimal("110")
    assert eur_client.get("/api/fund-prices").json()[0]["precio"] == 99.0
    assert usd_client.get("/api/fund-prices").json()[0]["precio"] == 100.0


@pytest.mark.django_db
def test_yahoo_refresh_persists_only_the_native_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eur_workspace, eur_client = workspace_client("refresh-eur", "EUR")
    usd_workspace, usd_client = workspace_client("refresh-usd", "USD")
    instrument = shared_instrument(eur_workspace, usd_workspace)
    FxRate.objects.create(
        quote_currency="USD",
        base_currency="EUR",
        rate_date=date.today(),
        rate=Decimal("0.9"),
        source="yahoo",
    )
    monkeypatch.setattr(views, "yahoo_ticker", lambda _instrument: "TEST")
    monkeypatch.setattr(views, "quote_price", lambda _ticker: (100.0, "USD"))

    response = eur_client.post("/api/stock-prices/fetch", format="json")

    assert response.status_code == 200
    assert response.json()["results"][0]["precio"] == 90.0
    stored = MarketPrice.objects.get(instrument=instrument, source="yahoo")
    assert stored.close == Decimal("100")
    assert stored.currency == "USD"
    assert usd_client.get("/api/stock-prices").json()[0]["precio"] == 100.0


@pytest.mark.django_db
@pytest.mark.parametrize("price", [None, "-1"])
def test_manual_price_rejects_missing_or_negative_values(price: str | None) -> None:
    workspace, client = workspace_client("invalid-price", "EUR")
    instrument = Instrument.objects.create(
        kind=Instrument.Kind.FUND,
        name="Fund",
        quote_currency="EUR",
    )
    InstrumentIdentifier.objects.create(
        instrument=instrument,
        scheme=InstrumentIdentifier.Scheme.ISIN,
        value="TEST00000002",
        is_primary=True,
    )
    WorkspaceInstrument.objects.create(workspace=workspace, instrument=instrument)

    response = client.put(
        "/api/fund-prices/TEST00000002",
        {"precio": price, "moneda": "EUR"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_provider_failure_never_falls_back_to_an_identity_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, client = workspace_client("provider-failure", "EUR")
    instrument = shared_instrument(workspace, kind=Instrument.Kind.FUND)
    monkeypatch.setattr(views, "yahoo_ticker", lambda _instrument: "TEST")
    monkeypatch.setattr(views, "quote_price", lambda _ticker: (100.0, "USD"))

    def unavailable(*_args: object, **_kwargs: object) -> NoReturn:
        raise CurrencyConversionError("No USD/EUR rate")

    monkeypatch.setattr(views, "rate_to_base", unavailable)

    response = client.post("/api/fund-prices/fetch")

    assert response.status_code == 200
    assert response.json()["results"] == [
        {"isin": "TEST00000001", "precio": None, "error": "No USD/EUR rate"}
    ]
    assert not MarketPrice.objects.filter(instrument=instrument).exists()
    assert WorkspaceMarketPriceOverride.objects.count() == 0
