from pathlib import Path

from django.conf import settings

from finanzr import __version__


def test_openapi_uses_the_canonical_application_version() -> None:
    assert settings.SPECTACULAR_SETTINGS["VERSION"] == __version__


def test_version_matches_the_repository_source() -> None:
    version_file = Path(__file__).resolve().parents[2] / "VERSION"
    assert __version__ == version_file.read_text(encoding="utf-8").strip()
