"""Read the application version from the repository release source."""

from __future__ import annotations

from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parents[1] / "VERSION"


def read_version() -> str:
    """Return the release version embedded in the source tree."""
    try:
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:  # pragma: no cover - packaging failure, not an application state
        raise RuntimeError(f"Unable to read Finanzr version from {VERSION_FILE}") from exc
    if not version:
        raise RuntimeError(f"Finanzr version is empty in {VERSION_FILE}")
    return version


__version__ = read_version()
