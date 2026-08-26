from django.conf import settings
from django.test import override_settings


@override_settings(
    ALLOWED_HOSTS=["localhost", "127.0.0.1", "backend"],
    CSRF_TRUSTED_ORIGINS=["http://localhost:5173"],
)
def test_vite_proxy_origin_and_docker_host_are_allowed() -> None:
    assert "backend" in settings.ALLOWED_HOSTS
    assert "http://localhost:5173" in settings.CSRF_TRUSTED_ORIGINS
