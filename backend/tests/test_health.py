import pytest
from django.test import Client
from django.urls import resolve, reverse


@pytest.mark.django_db
def test_health_check_includes_database_status(client: Client) -> None:
    response = client.get(reverse("health-check"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_openapi_schema_is_available(client: Client) -> None:
    response = client.get(reverse("api-schema"))

    assert response.status_code == 200
    assert "application/vnd.oai.openapi" in response["Content-Type"]
    assert b"/api/health/" in response.content


@pytest.mark.django_db
def test_retired_kraken_upload_alias_returns_404(client: Client) -> None:
    response = client.post("/api/crypto-orders/upload-kraken")

    assert response.status_code == 404
    assert resolve("/api/crypto-orders/upload-kraken-pro").route == (
        "api/crypto-orders/upload-kraken-pro"
    )


@pytest.mark.django_db
def test_admin_requires_authentication(client: Client) -> None:
    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
    assert reverse("admin:login") in response["Location"]
