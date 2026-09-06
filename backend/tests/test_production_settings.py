import json
import os
import subprocess
import sys
from typing import cast


def production_security_flags(lan_mode: bool) -> dict[str, object]:
    script = """
import json
from config.settings import production

print(json.dumps({
    "csrf_secure": production.CSRF_COOKIE_SECURE,
    "hsts": production.SECURE_HSTS_SECONDS,
    "proxy": production.SECURE_PROXY_SSL_HEADER,
    "redirect": production.SECURE_SSL_REDIRECT,
    "session_secure": production.SESSION_COOKIE_SECURE,
}))
"""
    environment = {
        **os.environ,
        "DJANGO_SECRET_KEY": "test-only-production-secret",
        "DJANGO_SECURE_HSTS_SECONDS": "31536000",
        "DJANGO_SECURE_SSL_REDIRECT": "true",
        "FINANZR_LAN_MODE": "1" if lan_mode else "0",
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    return cast(dict[str, object], json.loads(result.stdout))


def production_cache_settings(location: str = "/tmp/finanzr-cache") -> dict[str, str]:
    script = """
import json
from config.settings import production

print(json.dumps({
    "backend": production.CACHES["default"]["BACKEND"],
    "location": production.CACHES["default"]["LOCATION"],
}))
"""
    environment = {
        **os.environ,
        "DJANGO_SECRET_KEY": "test-only-production-secret",
        "DJANGO_CACHE_LOCATION": location,
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    return cast(dict[str, str], json.loads(result.stdout))


def test_production_defaults_keep_https_security() -> None:
    assert production_security_flags(lan_mode=False) == {
        "csrf_secure": True,
        "hsts": 31536000,
        "proxy": ["HTTP_X_FORWARDED_PROTO", "https"],
        "redirect": True,
        "session_secure": True,
    }


def test_explicit_lan_mode_allows_http_sessions_without_hsts() -> None:
    assert production_security_flags(lan_mode=True) == {
        "csrf_secure": False,
        "hsts": 0,
        "proxy": None,
        "redirect": False,
        "session_secure": False,
    }


def test_production_uses_configurable_file_cache() -> None:
    assert production_cache_settings() == {
        "backend": "django.core.cache.backends.filebased.FileBasedCache",
        "location": "/tmp/finanzr-cache",
    }
    assert production_cache_settings("/tmp/synthetic-finanzr-cache") == {
        "backend": "django.core.cache.backends.filebased.FileBasedCache",
        "location": "/tmp/synthetic-finanzr-cache",
    }
