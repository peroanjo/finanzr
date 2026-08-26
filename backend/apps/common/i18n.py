from __future__ import annotations

from typing import Any

from django.utils import translation

from apps.common.models import InstallationSettings

SPANISH = str(InstallationSettings.Language.SPANISH)
ENGLISH = str(InstallationSettings.Language.ENGLISH)
SUPPORTED_LANGUAGES = {SPANISH, ENGLISH}


def normalize_language(value: object) -> str | None:
    """Return the public language code supported by Finanzr."""

    raw = str(value or "").strip().replace("_", "-").casefold()
    if raw == "en" or raw.startswith("en-"):
        return ENGLISH
    if raw == "es" or raw.startswith("es-"):
        return SPANISH
    return None


def language_from_accept_header(header: str) -> str | None:
    weighted: list[tuple[float, int, str]] = []
    for index, item in enumerate(header.split(",")):
        parts = [part.strip() for part in item.split(";")]
        if not parts or parts[0] == "*":
            continue
        quality = 1.0
        for parameter in parts[1:]:
            if parameter.casefold().startswith("q="):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        language = normalize_language(parts[0])
        if language and quality > 0:
            weighted.append((quality, -index, language))
    return max(weighted, default=(0.0, 0, ""))[2] or None


def installation_language(request: Any | None = None) -> str:
    language = getattr(request, "finanzr_default_language", "") if request else ""
    return normalize_language(language) or InstallationSettings.load().default_language


def effective_language(user: Any | None = None, request: Any | None = None) -> str:
    preferred = normalize_language(getattr(user, "language", "")) if user else None
    return preferred or installation_language(request)


def activate_request_language(request: Any, language: str) -> None:
    request.LANGUAGE_CODE = language
    underlying_request = getattr(request, "_request", None)
    if underlying_request is not None:
        underlying_request.LANGUAGE_CODE = language
    translation.activate(language)
